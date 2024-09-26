import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup, NavigableString
import openai
import re
import argparse
import toml
import os
import json
from openai import OpenAI
from tqdm.auto import tqdm
import time
from tenacity import retry, stop_after_attempt, wait_random_exponential

class RateLimiter:
    def __init__(self, calls_per_minute):
        self.calls_per_minute = calls_per_minute
        self.interval = 60 / calls_per_minute
        self.last_call_time = 0

    def wait(self):
        current_time = time.time()
        time_since_last_call = current_time - self.last_call_time
        if time_since_last_call < self.interval:
            time.sleep(self.interval - time_since_last_call)
        self.last_call_time = time.time()

# 创建一个全局的 RateLimiter 实例
rate_limiter = RateLimiter(calls_per_minute=20)  # 每分钟20次调用

@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(5))
def call_openai_api(client, model, messages):
    rate_limiter.wait()  # 在每次 API 调用前等待
    try:
        return client.chat.completions.create(model=model, messages=messages)
    except Exception as e:
        print(f"API调用失败: {str(e)}. 正在重试...")
        time.sleep(5)  # 在重试之前等待5秒
        raise

def load_vocabulary(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            return set(word.strip().lower() for word in file)
    return set()

def is_code_or_formula(tag):
    # 检查是否为代码块或数学公式
    return tag.name in ['code', 'pre'] or tag.get('class') in ['code', 'math', 'formula']

def extract_important_words(paragraph, model, client, exclude_words):
    # 使用 OpenAI API 从段落中提取重要词汇
    response = call_openai_api(
        client,
        model,
        [
            {"role": "system", "content": "你是一个英语教育专家,需要从给定段落中提取重要且有一定难度的英文高频词汇。"},
            {"role": "user", "content": f"请从以下段落中提取0到8个重要且有一定难度的英文高频词汇,只需列出这些词汇,用逗号分隔,如果一个词汇都没有,请返回空字符串。\n\n段落内容：{paragraph}"}
        ]
    )
    return [word.strip() for word in response.choices[0].message.content.split(',') if word.strip() and word.strip().lower() not in exclude_words]

def get_translations(words, model, client):
    if not words:
        return {}
    words_str = ', '.join(words)
    response = call_openai_api(
        client,
        model,
        [
            {"role": "system", "content": "你是一个英汉翻译专家。"},
            {"role": "user", "content": f"请将以下英文单词翻译成中文,给出简洁的翻译,不要解释。每个翻译用逗号分隔。如果无法翻译某个单词，请保留原单词:\n\n{words_str}"}
        ]
    )
    translations = response.choices[0].message.content.split(',')
    return {word: translation.strip() for word, translation in zip(words, translations)}

def process_content(content, model, client, exclude_words):
    soup = BeautifulSoup(content, 'html.parser')
    paragraphs = soup.find_all('p')
    
    # 收集所有非代码、非公式的文本
    batch_size = 5000  # 每批处理的字符数
    current_batch = ""
    important_words = set()

    # 使用tqdm.auto来创建嵌套的进度条
    for paragraph in tqdm(paragraphs, desc="处理段落", leave=False):
        for child in paragraph.children:
            if isinstance(child, NavigableString) and not is_code_or_formula(child.parent):
                current_batch += child.string + " "
                if len(current_batch) >= batch_size:
                    batch_important_words = extract_important_words(current_batch, model, client, exclude_words)
                    important_words.update(batch_important_words)
                    current_batch = ""

    # 处理最后一批
    if current_batch:
        batch_important_words = extract_important_words(current_batch, model, client, exclude_words)
        important_words.update(batch_important_words)

    # 获取所有重要词汇的翻译
    translations = get_translations(list(important_words), model, client)
    replaced_words = set()  # 用于跟踪在当前段落中已替换的词
    for paragraph in paragraphs:
        new_contents = []
        for child in paragraph.children:
            if isinstance(child, NavigableString) and not is_code_or_formula(child.parent):
                text = child.string
                for word in important_words:
                    if word not in replaced_words and word in translations and translations[word].lower() != word.lower():
                        pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
                        replacement = f'<ruby>{word}<rt>{translations[word]}</rt></ruby>'
                        text, count = pattern.subn(replacement, text, count=1)  # 只替换一次
                        if count > 0:
                            replaced_words.add(word)
                new_contents.append(BeautifulSoup(text, 'html.parser'))
            else:
                new_contents.append(child)
        paragraph.clear()
        paragraph.extend(new_contents)
    
    return str(soup)

def load_config(config_file):
    if os.path.exists(config_file):
        return toml.load(config_file)
    return {}

def save_progress(progress_file, processed_items, book):
    with open(progress_file, 'w') as f:
        json.dump({
            'processed_items': list(processed_items),
            'book_content': {item.id: item.get_content().decode('utf-8') for item in book.get_items() if item.get_type() == ebooklib.ITEM_DOCUMENT}
        }, f)

def load_progress(progress_file, book):
    if os.path.exists(progress_file):
        with open(progress_file, 'r') as f:
            data = json.load(f)
            processed_items = set(data['processed_items'])
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT and item.id in data['book_content']:
                    item.set_content(data['book_content'][item.id].encode('utf-8'))
            return processed_items
    return set()

def main():
    parser = argparse.ArgumentParser(description='处理EPUB文件,为重要英文词汇添加注释。')
    parser.add_argument('input_file', help='输入的EPUB文件路径')
    parser.add_argument('output_file', help='输出的EPUB文件路径')
    parser.add_argument('--config', default='config.toml', help='配置文件路径')
    parser.add_argument('--api_key', help='OpenAI API密钥')
    parser.add_argument('--base_url', help='OpenAI API基础URL')
    parser.add_argument('--model', help='OpenAI 模型名称')
    parser.add_argument('--vocab', default='vocabulary.txt', help='词汇表文件路径')
    parser.add_argument('--progress', default='progress.json', help='进度文件路径')
    
    args = parser.parse_args()

    # 加载配置文件
    config = load_config(args.config)

    # 命令行参数优先级高于配置文件
    api_key = args.api_key or config.get('openai', {}).get('api_key')
    base_url = args.base_url or config.get('openai', {}).get('base_url')
    model = args.model or config.get('openai', {}).get('model')

    if not api_key:
        raise ValueError("API密钥必须在配置文件或命令行参数中提供")

    # 加载词汇表
    exclude_words = load_vocabulary(args.vocab)

    # 设置 OpenAI API
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=10, max_retries=5)

    # 打开 EPUB 文件
    book = epub.read_epub(args.input_file)

    # 加载进度
    processed_items = load_progress(args.progress, book)

    # 获取所有需要处理的项目
    items_to_process = [item for item in book.get_items() if item.get_type() == ebooklib.ITEM_DOCUMENT]

    # 使用 tqdm 创建外层进度条
    for item in tqdm(items_to_process, desc="处理章节"):
        if item.id not in processed_items:
            content = item.get_content().decode('utf-8')
            processed_content = process_content(content, model, client, exclude_words)
            item.set_content(processed_content.encode('utf-8'))
            processed_items.add(item.id)
            
            # 每处理完一个项目就保存进度
            save_progress(args.progress, processed_items, book)

    # 保存修改后的 EPUB 文件
    epub.write_epub(args.output_file, book)

    print(f"处理完成。输出文件: {args.output_file}")

    # 处理完成后删除进度文件
    if os.path.exists(args.progress):
        os.remove(args.progress)

if __name__ == "__main__":
    main()
