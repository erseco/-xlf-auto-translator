# xlf-auto-translator

`xlf-auto-translator` is a Python script designed to simplify and automate the translation of `.xlf` files. It identifies untranslated strings in the XML content and translates them using an AI-based translation engine. The script supports OpenAI's API and is compatible with other translation engines.

## Features

- **Automated Translation:** Quickly translate untranslated strings in `.xlf` files.
- **AI-Powered:** Compatible with OpenAI and other translation engines.
- **Customizable:** Easily adapt the script to work with your preferred translation service.
- **Standards-Compliant:** Works seamlessly with `.xlf` files adhering to the XLIFF standard.

## Installation

### Requirements

- Python 3.7 or higher
- An API key for the translation engine of your choice (e.g., OpenAI's API)

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/erseco/xlf-auto-translator.git
   cd xlf-auto-translator
   ```

2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up your API key:
   Create a `.env` file in the project directory and add your API key:
   ```
   OPENAI_API_KEY=your_api_key_here
   OPENAI_API_URL=https://api.openai.com/v1
   ```

## Usage

The script provides several options for translating XLF files:

```bash
python translate.py <input-file.xlf> [options]
```

### Options

- `--language`, `-l`: Target language (e.g., es, fr, de). If not provided, will try to detect from filename
- `--inline`, `-i`: Edit file in-place instead of creating a new file
- `--force`, `-f`: Force translation of all strings, even if already translated

### Examples

Basic usage (creates a new translated file):
```bash
python translate.py messages.es.xlf
```

Specify target language explicitly:
```bash
python translate.py messages.xlf --language es
```

Edit file in-place:
```bash
python translate.py messages.es.xlf --inline
```

Force retranslation of all strings:
```bash
python translate.py messages.es.xlf --force
```

## Configuration

Configure the OpenAI API settings in your `.env` file:

```
OPENAI_API_KEY=your_openai_api_key
OPENAI_API_URL=https://api.openai.com/v1
```

### Features

- Automatic language detection from filename
- Preserves XML structure and formatting
- Maintains CDATA sections and HTML entities
- Batch processing to optimize API usage
- Progress bar for translation status
- Statistics about translated/untranslated strings
- Interactive confirmation before translation

## Roadmap

- Add support for additional translation engines.
- Implement batch processing for multiple `.xlf` files.
- Provide detailed logs for the translation process.
- Include a fallback mechanism for untranslated strings.

## Contributing

Contributions are welcome! Feel free to submit issues, feature requests, or pull requests.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

---

For questions or suggestions, feel free to contact us or open an issue in the repository.

