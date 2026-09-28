\# Contributing Translations / 贡献翻译



\[English](#english) | \[中文](#中文)



\---



\## English



\### How to add a new language



1\. Copy `translations/en.json` to `translations/<language\_code>.json`

2\. Edit the `meta` field:

&#x20;  - `language\_name`: your language name (in your language)

&#x20;  - `language\_code`: ISO 639-1 code (e.g. `ja`, `ko`, `fr`)

&#x20;  - `font\_family`: recommended font (can be empty)

3\. Translate all texts in the `texts` field

4\. Submit a Pull Request



\### Example



For Japanese, file name `ja.json`:



{

&#x20; "meta": {

&#x20;   "language\_name": "日本語",

&#x20;   "language\_code": "ja",

&#x20;   "font\_family": "Yu Gothic",

&#x20;   "font\_size\_default": 13

&#x20; },

&#x20; "texts": {

&#x20;   "app\_title": "ファイル同期ツール",

&#x20;   ...

&#x20; }

}



\### Notes



\- Do not modify the keys (e.g. `app\_title`), only translate the values

\- If unsure about a translation, you can keep the English text

\- Partial translations are OK — missing keys will fall back to Chinese or English



\---



\## 中文



\### 如何添加一种新语言



1\. 复制 `translations/en.json` 为 `translations/<语言代码>.json`

2\. 修改 `meta` 字段：

&#x20;  - `language\_name`：你的语言名称（用你的语言写）

&#x20;  - `language\_code`：ISO 639-1 语言代码（如 `ja`、`ko`、`fr`）

&#x20;  - `font\_family`：推荐字体（可留空使用默认）

3\. 翻译 `texts` 中的所有文本

4\. 提交 Pull Request



\### 示例



以日语为例，文件名为 `ja.json`：



（同上示例）



\### 注意事项



\- 不要修改 `texts` 中的 key（如 `app\_title`），只翻译 value

\- 如果有不确定的翻译，可以保留英文

\- 翻译不完整也没关系，缺失的部分会自动 fallback 到中文或英文

