
import json, os, re, sys
import argparse
from googletrans import Translator  # Importing Google Translator from googletrans
from tqdm import tqdm  # For progress bar
from time import sleep

# Function to create the translator instance
def get_translator(debug=False):
    try:
        if debug:
            print(f"Initializing Google Translator...")
        
        translator_instance = Translator()
        
        if debug:
            print(f"Google Translator initialized successfully.")
        
        return translator_instance
    
    except Exception as e:
        print(f"Error initializing the translator: {e}")
        sys.exit(1)
     
def safe_translate(translator, text, src_language, dest_language, delay=10):
    retries = 3
    for i in range(retries):
        try:
            return translator.translate(text, src=src_language, dest=dest_language).text
        except Exception as e:
            print(f"Error translating: {e}. Trying again ({i+1}/{retries})...")
            sleep(delay)
    raise Exception(f"Failed to translate after {retries} attempts.")

# -------------------- Translate comments and prints ------------------------------
def translate_code_comments_and_prints(code, translator, src_language, dest_language, delay):
    lines = code.split('\n')
    translated_lines = []

    for line in lines:
        if line.strip().startswith('#<---'):
            # Ignore comments starting with '#<---'
            translated_lines.append(line)
        elif '#' in line:
            # Split the line into code and comment parts
            code_part, comment_part = line.split('#', 1)
            if not comment_part.strip().startswith('<---'):
                # Translate the comment part using safe_translate
                translated_comment = safe_translate(translator, comment_part.strip(), src_language, dest_language, delay=delay)
                # Reconstruct the line with translated comment
                translated_lines.append(f"{code_part}# {translated_comment}")
            else:
                # If the comment starts with '<---', keep it as is
                translated_lines.append(line)
        elif re.search(r'print\(\s*f[\"\']', line):
            # Handle formatted print statements
            print_match = re.search(r'print\(\s*f([\"\'])(.*?)(\1)\)', line)
            if print_match:
                text_part = print_match.group(2)
                
                # Find variables within the curly braces and separate them from the text
                variables = re.findall(r'\{.*?\}', text_part)
                translated_text = text_part
                
                # Translate only the text outside the curly braces
                for var in variables:
                    translated_text = translated_text.replace(var, "VARIABLE_PLACEHOLDER")
                
                translated_text = safe_translate(translator, translated_text, src_language, dest_language, delay=delay)
                
                # Replace the placeholders back with the original variables
                for var in variables:
                    translated_text = translated_text.replace("VARIABLE_PLACEHOLDER", var, 1)
                
                # Reconstruct the print statement
                formatted_print = re.sub(r'print\(\s*f([\"\'])(.*?)(\1)\)', 
                                         f'print(f"{translated_text}")', 
                                         line)
                translated_lines.append(formatted_print)
            else:
                translated_lines.append(line)
        else:
            translated_lines.append(line)

    return '\n'.join(translated_lines)


# -------------------- Translate Markdown -----------------------------------------
def translate_markdown(text, translator, src_language, dest_language, delay):
    # Use safe_translate to translate the text and return the result
    return safe_translate(translator, text, src_language, dest_language, delay=delay)


# -------------------- Main Case --------------------------------------------------
def jupyter_translate(fname, src_language, dest_language, delay, rename_source_file=False, print_translation=False, debug=False):
    """
    Translates a Jupyter Notebook from one language to another.
    """

    # Initialize the translator
    translator = get_translator(debug)

    # Check if the necessary parameters are provided
    if not fname or not dest_language:
        print("Error: Missing required parameters.")
        print("Usage: python jupyter_translate.py <notebook_file> --source <source_language> --target <destination_language>")
        sys.exit(1)

    # Load the notebook file
    with open(fname, 'r', encoding='utf-8') as file:
        data_translated = json.load(file)

    total_cells = len(data_translated['cells'])
    code_cells = sum(1 for cell in data_translated['cells'] if cell['cell_type'] == 'code')
    markdown_cells = sum(1 for cell in data_translated['cells'] if cell['cell_type'] == 'markdown')

    print(f"Total cells: {total_cells} Code cells: {code_cells} Markdown cells: {markdown_cells}")

    # ------ translation zone ---------
    for i, cell in enumerate(tqdm(data_translated['cells'], desc="Translating cells", unit="cell")):
        if cell['cell_type'] == 'markdown':
            # Concatenate all lines of the Markdown cell into a single block of text
            source = ''.join(cell['source'])
            
            if debug:
                print(f'Cell {i} Markdown (before translation): {source}')
            
            # Translate the entire block of text
            translated_text = translate_markdown(source, translator, src_language, dest_language, delay=delay)
            
            # Update the cell with the translated text
            data_translated['cells'][i]['source'] = [translated_text]
            
            if debug:
                print(f'Cell {i} Markdown (after translation): {translated_text}')
    
        elif cell['cell_type'] == 'code':
            # Concatenate all lines of the code cell into a single block of text
            source = ''.join(cell['source'])
            
            if debug:
                print(f'Cell {i} Code (before translation): {source}')
            
            # Translate the entire block of code, focusing on comments and formatted print statements
            translated_text = translate_code_comments_and_prints(source, translator, src_language, dest_language, delay=delay)
            
            # Update the cell with the translated text
            data_translated['cells'][i]['source'] = [translated_text]
            
            if debug:
                print(f'Cell {i} Code (after translation): {translated_text}')
    
        if print_translation:
            print(f'Translated Cell {i}: {data_translated["cells"][i]["source"]}')

    # ----- end of translation zone -----

    
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
    parser.add_argument('--rename', action='store_true', help="Rename the original file after translation")
    parser.add_argument('--print', dest='print_translation', action='store_true', help="Print translations to console")
    parser.add_argument('--debug', dest='debug', action='store_true', help="Produces a lot of msgs in your console")

    args = parser.parse_args()

    jupyter_translate(
        fname=args.fname,
        src_language=args.source,
        dest_language=args.target,
        delay=args.delay,
        rename_source_file=args.rename,
        print_translation=args.print_translation,
        debug=args.debug
    )

if __name__ == '__main__':
    main()
