#  epub-vocab-annotator 

 epub-vocab-annotator 是一个为 EPUB 电子书提供英文词汇注释的工具，它通过 OpenAI 的语言模型来识别关键词汇，并提供精准的翻译，帮助读者更好地理解和学习英文词汇。

 <img width="916" alt="image" src="https://github.com/user-attachments/assets/b2bc00e5-fc7e-4819-bf93-d3ad2e6cb4e7">


## 功能特点

- 自动识别 EPUB 文件中的重要或困难英文词汇
- 为识别出的词汇添加准确的中文翻译注释
- 使用 `<ruby>` 标签添加注释,确保阅读体验流畅
- 支持通过 TOML 配置文件或命令行参数自定义 OpenAI API 设置
- 允许选择不同的 OpenAI 语言模型
- 保留原始 EPUB 文件的格式和样式
- 智能跳过代码块和数学公式,保持特殊内容的完整性
- 支持自定义词汇表,排除不需要注释的单词
- 显示处理进度,方便用户了解任务完成情况
- 支持中断恢复,可以从上次处理的位置继续
- 支持处理大型章节，自动拆分内容以提高效率和稳定性

## 安装

1. 克隆此仓库:
   ```
   git clone https://github.com/wayhome/epub-vocab-annotator.git
   cd epub-vocab-annotator
   ```

2. 安装所需依赖:
   ```
   uv sync
   ```

## 配置

1. 创建一个名为 `config.toml` 的文件,设置 OpenAI API:

```toml
[openai]
api_key = "your_api_key_here"
base_url = "https://api.openai.com/v1"
model = "gpt-3.5-turbo"
```

2. 创建一个名为 `vocabulary.txt` 的文件,每行一个单词,列出不需要注释的单词。

## 使用方法

```
uv run main.py input.epub output.epub --config config.toml --vocab vocabulary.txt --progress progress.json
```

## 参数说明

- `input_file`: 输入的 EPUB 文件路径
- `output_file`: 输出的 EPUB 文件路径
- `--config`: 配置文件路径 (默认: `config.toml`)
- `--api_key`: OpenAI API 密钥
- `--base_url`: OpenAI API 基础 URL (默认: `https://api.openai.com/v1`)
- `--model`: OpenAI 语言模型名称 (默认: `gpt-3.5-turbo`)
- `--vocab`: 词汇表文件路径 (默认: `vocabulary.txt`)
- `--progress`: 进度文件路径 (默认: `progress.json`)

## 注意事项

- 本工具会自动跳过代码块和数学公式,以保持这些特殊内容的完整性
- 词汇表中的单词不会被添加注释
- 请确保您有足够的 OpenAI API 使用额度
- 处理大型 EPUB 文件可能需要较长时间
- 建议在使用前备份原始 EPUB 文件
- 处理过程中会显示进度条,方便了解任务完成情况
- 如果处理过程中断,可以使用相同的命令重新运行,工具会从上次中断的位置继续处理,并保留之前的所有修改

## 贡献

欢迎提交 issues 和 pull requests 来帮助改进这个项目!

## 许可证

本项目采用 MIT 许可证。详情请见 [LICENSE](LICENSE) 文件。
