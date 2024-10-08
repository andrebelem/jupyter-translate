"""
History:
- 08 Aug 2024: Introduced argparse for handling command-line arguments, including options for specifying input (--source) and output (--target) languages, as well as the file path.
- 09 Aug 2024: Migrated from googletrans to deep-translator for enhanced translation stability and compatibility.
- 09 Aug 2024: Implemented error handling for missing required parameters (--source and --target).
- 12 Aug 2024: Set the default --source language to 'en' and introduced retry attempts with a delay (default 15 seconds) to prevent API rate limits with deep-translator.
- 12 Aug 2024: Added support for selecting different translators using --translator, with googletrans as the default.
- 20 Aug 2024: Corrected handling of horizontal lines '---' and empty "NONE" tags.
- 20 Aug 2024: Enhanced the program to preserve active links in markdown, as well as embedded code, LaTeX equations, and LaTeX code blocks.
"""

import json, os, re, sys
import argparse
from deep_translator import (
    GoogleTranslator,
    MyMemoryTranslator
)
from tqdm import tqdm  # For progress bar
from time import sleep

# Função para selecionar o tradutor com base no nome
def get_translator(translator_name, src_language, dest_language):
    translators = {
        'google': GoogleTranslator,
        'mymemory': MyMemoryTranslator,
    }
    TranslatorClass = translators.get(translator_name.lower())
    if not TranslatorClass:
        raise ValueError(f"Translator {translator_name} not supported.")
    
    try:
        print(f"Using translator: {translator_name.capitalize()}")
        return TranslatorClass(source=src_language, target=dest_language)
    except Exception as e:
        if 'No support for the provided language' in str(e):
            print(f"Erro: {e}")
            supported_languages = TranslatorClass().get_supported_languages(as_dict=True)
            print(f"Supported languages {translator_name}: {supported_languages}")
        else:
            print(f"Error initializing the translator: {e}")
        sys.exit(1)

def safe_translate(translator, text, retries=3, delay=10):
    for i in range(retries):
        try:
            return translator.translate(text)
        except Exception:
            print(f"Error translating. Trying again ({i+1}/{retries})...")
            sleep(delay)
    raise Exception(f"Fail to translate after {retries} attempts.")

def translate_markdown(text, translator, delay=0):
    # Handle the case where `text` is None right at the beginning
    if text is None:
        return None  # Or you could return an empty string if that suits your needs better

    # Define necessary constants and regex expressions
    END_LINE = '\n'
    IMG_PREFIX = '!['
    HEADERS = ['### ', '###', '## ', '##', '# ', '#']  # Should be processed in this order (bigger to smaller)
    
    MD_CODE_REGEX = r'```[a-z]*\n[\s\S]*?\n```'  # Triple backticks code blocks
    INDENTED_CODE_REGEX = r'^(?!\s*[-*]\s|\s*\d+\.\s|```).*[ ]{4,}.*'  # Indented code blocks (excluding lists, tables, and triple backticks)
    INLINE_LATEX_REGEX = r'\$[^\$]+\$'  # Inline LaTeX between $...$
    DISPLAY_LATEX_REGEX = r'\$\$[^\$]+\$\$'  # Displayed LaTeX between $$...$$
    EQUATION_ENV_REGEX = r'\\begin\{equation\}[\s\S]*?\\end\{equation\}'  # LaTeX \begin{equation}...\end{equation}
    LINK_REGEX = r'\[([^\]]+)\]\(([^)]+)\)'  # Markdown links
    HTML_TAG_REGEX = r'<(img|video|a)\b[^>]*>'  # Specific HTML tags: img, video, a
    ANGLE_BRACKET_URL_REGEX = r'<(https?://[^>]+)>'  # URLs enclosed in angle brackets
    LATEX_COMMAND_REGEX = r'\\[a-zA-Z]+\{[^\}]+\}'  # LaTeX command structure like \xxx{yyy}

    # Replacement keywords
    CODE_REPLACEMENT_KW = 'xx_markdown_code_xx'
    LATEX_REPLACEMENT_KW = 'xx_latex_code_xx'
    LINK_REPLACEMENT_KW = 'xx_markdown_link_xx'
    HTML_TAG_REPLACEMENT_KW = 'xx_html_tag_xx'
    ANGLE_BRACKET_URL_REPLACEMENT_KW = 'xx_angle_bracket_url_xx'
    LATEX_COMMAND_REPLACEMENT_KW = 'xx_latex_command_xx'

    # Check for indented code blocks and issue a warning
    if re.search(INDENTED_CODE_REGEX, text):
        print(f"Warning: Detected indented code blocks. Consider verifying the indentation of the code block! [code]:{text}")

    # Inner function to replace tags from text from a source list
    def replace_from_list(tag, text, replacement_list):
        try:
            if text is None:
                return None
            
            if tag is None or tag == "---":
                return tag
            
            if not isinstance(text, (str, bytes)):
                raise TypeError(f"Expected string or bytes-like object for 'text', but got {type(text).__name__}")
    
            if not isinstance(tag, str):
                raise TypeError(f"Expected string for 'tag', but got {type(tag).__name__}")
    
            list_to_gen = lambda: [(x) for x in replacement_list]
            replacement_gen = list_to_gen()
    
            return re.sub(tag, lambda x: next(iter(replacement_gen)), text)
        
        except Exception as e:
            print(f"An error occurred while processing the text: {text}")
            raise e

    # Inner function for translation
    def translate(text):
        if text is None:
            return ''  # Return an empty string if `text` is None

        # Get all markdown code blocks, indented code blocks, LaTeX equations, links, HTML tags, URLs in angle brackets, and LaTeX commands
        md_codes = re.findall(MD_CODE_REGEX, text)
        indented_codes = re.findall(INDENTED_CODE_REGEX, text)
        inline_latex = re.findall(INLINE_LATEX_REGEX, text)
        display_latex = re.findall(DISPLAY_LATEX_REGEX, text)
        equation_envs = re.findall(EQUATION_ENV_REGEX, text)
        links = re.findall(LINK_REGEX, text)
        html_tags = re.findall(HTML_TAG_REGEX, text)
        angle_bracket_urls = re.findall(ANGLE_BRACKET_URL_REGEX, text)
        latex_commands = re.findall(LATEX_COMMAND_REGEX, text)

        # Replace all identified blocks with placeholders
        text = re.sub(MD_CODE_REGEX, CODE_REPLACEMENT_KW, text)
        text = re.sub(INDENTED_CODE_REGEX, CODE_REPLACEMENT_KW, text)
        text = re.sub(INLINE_LATEX_REGEX, LATEX_REPLACEMENT_KW, text)
        text = re.sub(DISPLAY_LATEX_REGEX, LATEX_REPLACEMENT_KW, text)
        text = re.sub(EQUATION_ENV_REGEX, LATEX_REPLACEMENT_KW, text)
        text = re.sub(LINK_REGEX, LINK_REPLACEMENT_KW, text)
        text = re.sub(HTML_TAG_REGEX, HTML_TAG_REPLACEMENT_KW, text)
        text = re.sub(ANGLE_BRACKET_URL_REGEX, ANGLE_BRACKET_URL_REPLACEMENT_KW, text)
        text = re.sub(LATEX_COMMAND_REGEX, LATEX_COMMAND_REPLACEMENT_KW, text)

        # Translate the rest of the text
        text = safe_translate(translator, text, delay=delay)

        # Handle None case
        if text is None:
            text = ''  # If translation fails and returns None, use an empty string

        print(f"Replacement list: {angle_bracket_urls}")
              
        # Replace the placeholders with the original content
        text = replace_from_list(CODE_REPLACEMENT_KW, text, md_codes + indented_codes)
        text = replace_from_list(LATEX_REPLACEMENT_KW, text, inline_latex + display_latex + equation_envs)
        text = replace_from_list(LINK_REPLACEMENT_KW, text, links)
        text = replace_from_list(HTML_TAG_REPLACEMENT_KW, text, html_tags)
        text = replace_from_list(ANGLE_BRACKET_URL_REPLACEMENT_KW, text, angle_bracket_urls)
        text = replace_from_list(LATEX_COMMAND_REPLACEMENT_KW, text, latex_commands)

        return text

    # Check if there are special Markdown tags
    if len(text) >= 2:
        if text[-1:] == END_LINE:
            return translate(text) + '\n'

        if text[:2] == IMG_PREFIX:
            return text

        for header in HEADERS:
            len_header = len(header)
            if text[:len_header] == header:
                return header + translate(text[len_header:])

    return translate(text)

def translate_code_comments_and_prints(code, translator, delay):
    lines = code.split('\n')
    translated_lines = []
    for line in lines:
        if '#' in line:
            # Split the line into code and comment parts
            code_part, comment_part = line.split('#', 1)
            # Translate the comment part using safe_translate
            translated_comment = safe_translate(translator, comment_part.strip(), delay=delay)
            # Reconstruct the line with translated comment
            translated_lines.append(f"{code_part}# {translated_comment}")
        elif 'print(f"' in line or "print(f'" in line:
            # Handle formatted print statements
            print_match = re.search(r'print\((f?)(["\'])(.*?)(\2)\)', line)
            if print_match:
                print_part = print_match.group(1)
                text_part = print_match.group(3)
                # Translate only the text within the formatted print statement
                translated_text = safe_translate(translator, text_part, delay=delay)
                # Reconstruct the line with translated text
                translated_lines.append(f'print({print_part}"{translated_text}")')
            else:
                translated_lines.append(line)  # If it doesn't match, keep the line as is
        else:
            translated_lines.append(line)
    return '\n'.join(translated_lines)



def jupyter_translate(fname, src_language, dest_language, delay, translator_name, rename_source_file=False, print_translation=False):
    """
    Translates a Jupyter Notebook from one language to another.
    """

    # Initialize the translator
    translator = get_translator(translator_name, src_language, dest_language)

    # Check if the necessary parameters are provided
    if not fname or not dest_language:
        print("Error: Missing required parameters.")
        print("Usage: python jupyter_translate.py <notebook_file> --source <source_language> --target <destination_language> --translator <translator>")
        sys.exit(1)

    # Load the notebook file
    with open(fname, 'r', encoding='utf-8') as file:
        data_translated = json.load(file)

    total_cells = len(data_translated['cells'])
    code_cells = sum(1 for cell in data_translated['cells'] if cell['cell_type'] == 'code')
    markdown_cells = sum(1 for cell in data_translated['cells'] if cell['cell_type'] == 'markdown')

    print(f"Total cells: {total_cells} Code cells: {code_cells} Markdown cells: {markdown_cells}")

    skip_row = False
    for i, cell in enumerate(tqdm(data_translated['cells'], desc="Translating cells", unit="cell")):
        for j, source in enumerate(cell['source']):
            if cell['cell_type'] == 'markdown':
                if source[:3] == '```':
                    skip_row = not skip_row  # Invert flag until the next code block

                if not skip_row:
                    if source not in ['```\n', '```', '\n'] and source[:4] != '<img':  # Don't translate because of:
                        # 1. ``` -> ëëë 2. '\n' disappeared 3. image links damaged
                        data_translated['cells'][i]['source'][j] = \
                            translate_markdown(source, translator, delay=delay)
            elif cell['cell_type'] == 'code':
                # Translate comments and formatted print statements within code cells
                data_translated['cells'][i]['source'][j] = \
                    translate_code_comments_and_prints(source, translator, delay=delay)

            if print_translation:
                print(data_translated['cells'][i]['source'][j])

    if rename_source_file:
        fname_bk = f"{'.'.join(fname.split('.')[:-1])}_bk.ipynb"  # index.ipynb -> index_bk.ipynb

        os.rename(fname, fname_bk)
        print(f'{fname} has been renamed as {fname_bk}')

        with open(fname, 'w', encoding='utf-8') as f:
            json.dump(data_translated, f, ensure_ascii=False, indent=2)
        print(f'The {dest_language} translation has been saved as {fname}')
    else:
        dest_fname = f"{'.'.join(fname.split('.')[:-1])}_{dest_language}.ipynb"  # any.name.ipynb -> any.name_en.ipynb
        with open(dest_fname, 'w', encoding='utf-8') as f:
            json.dump(data_translated, f, ensure_ascii=False, indent=2)
        print(f'The {dest_language} translation has been saved as {dest_fname}')

# Main function to parse arguments and run the translation
def main():
    parser = argparse.ArgumentParser(description="Translate a Jupyter Notebook from one language to another.")
    parser.add_argument('fname', help="Path to the Jupyter Notebook file")
    parser.add_argument('--source', default='en', help="Source language code (default: en)")
    parser.add_argument('--target', required=True, help="Destination language code")
    parser.add_argument('--delay', type=int, default=10, help="Delay between retries in seconds (default: 10)")
    parser.add_argument('--translator', default='google', help="Translator to use (options: google or mymemory). Default: google")
    parser.add_argument('--rename', action='store_true', help="Rename the original file after translation")
    parser.add_argument('--print', dest='print_translation', action='store_true', help="Print translations to console")

    args = parser.parse_args()

    jupyter_translate(
        fname=args.fname,
        src_language=args.source,
        dest_language=args.target,
        delay=args.delay,
        translator_name=args.translator,
        rename_source_file=args.rename,
        print_translation=args.print_translation
    )

if __name__ == '__main__':
    main()


