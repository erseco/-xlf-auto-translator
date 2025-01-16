import argparse
import os
import sys
from pathlib import Path
import xml.etree.ElementTree as ET
from dotenv import load_dotenv
import openai
from tqdm import tqdm
import time
import shutil

# Load environment variables
load_dotenv()

# Configure OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")
BATCH_SIZE = 10  # Number of strings to translate in one API call

def extract_language_from_filename(filename):
    """Extract language code from filename (e.g., messages.es.xlf -> es)"""
    parts = Path(filename).stem.split('.')
    if len(parts) >= 2:
        return parts[-1]
    return None

def analyze_strings(tree):
    """Analyze strings in XLF file and return statistics"""
    total = 0
    untranslated = 0
    translated = 0
    
    # Register the XLIFF namespace
    ns = {'xliff': 'urn:oasis:names:tc:xliff:document:1.2'}
    
    for trans_unit in tree.findall(".//xliff:trans-unit", namespaces=ns):
        resname = trans_unit.get('resname')
        if resname:
            total += 1
            target = trans_unit.find('xliff:target', namespaces=ns)
            if target is None or not target.text or target.text.isspace():
                untranslated += 1
            else:
                translated += 1
            
    return {
        'total': total,
        'untranslated': untranslated,
        'translated': translated
    }

def translate_batch(texts, target_lang):
    """Translate a batch of texts using OpenAI's API"""
    try:
        messages = [
            {"role": "system", "content": f"You are a professional translator. Translate the following texts from English to {target_lang}. These are UI strings from a web application. Maintain any HTML or formatting tags unchanged. Return only the translations, one per line, maintaining the same order."},
            {"role": "user", "content": "\n".join(texts)}
        ]
        
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.3
        )
        
        translations = response.choices[0].message.content.strip().split('\n')
        return translations
    except Exception as e:
        print(f"Translation error: {e}")
        return None

def process_xlf_file(input_file, target_lang=None, inline=False, force=False):
    """Process XLF file and translate untranslated strings"""
    try:
        # Parse XLF file
        tree = ET.parse(input_file)
        root = tree.getroot()
        
        # Get target language
        if not target_lang:
            target_lang = extract_language_from_filename(input_file)
            if not target_lang:
                raise ValueError("Could not determine target language. Please specify with --language parameter.")
        
        # Analyze strings
        stats = analyze_strings(tree)
        print(f"\nFile analysis:")
        print(f"Total strings: {stats['total']}")
        print(f"Translated: {stats['translated']}")
        print(f"Untranslated: {stats['untranslated']}")
        
        if stats['untranslated'] == 0 and not force:
            print("\nNo untranslated strings found. Use --force to translate all strings.")
            return
        
        strings_to_translate = stats['total'] if force else stats['untranslated']
        print(f"\nWill translate {strings_to_translate} strings")
        print(f"Target language: {target_lang}")
        
        # Ask for confirmation
        response = input("Do you want to proceed with translation? (y/N): ")
        if response.lower() != 'y':
            print("Translation cancelled.")
            return
        
        # Register the XLIFF namespace
        ns = {'xliff': 'urn:oasis:names:tc:xliff:document:1.2'}
        
        # Collect strings to translate
        trans_units = []
        source_texts = []
        
        for trans_unit in root.findall(".//xliff:trans-unit", namespaces=ns):
            source = trans_unit.find('xliff:source', namespaces=ns)
            if source is not None and source.text:
                # Use the source text for translation
                source_text = source.text
                if force:
                    trans_units.append(trans_unit)
                    source_texts.append(source_text)
                else:
                    target = trans_unit.find('xliff:target', namespaces=ns)
                    if target is None or not target.text or target.text.isspace():
                        trans_units.append(trans_unit)
                        source_texts.append(source_text)
        
        # Translate in batches
        for i in tqdm(range(0, len(source_texts), BATCH_SIZE)):
            batch_texts = source_texts[i:i + BATCH_SIZE]
            batch_units = trans_units[i:i + BATCH_SIZE]
            
            translations = translate_batch(batch_texts, target_lang)
            if translations:
                for unit, translation in zip(batch_units, translations):
                    ns = {'xliff': 'urn:oasis:names:tc:xliff:document:1.2'}
                    target = unit.find('xliff:target', namespaces=ns)
                    if target is None:
                        target = ET.SubElement(unit, '{urn:oasis:names:tc:xliff:document:1.2}target')
                    # Only update if target is empty or force flag is set
                    if not target.text or target.text.isspace() or force:
                        if '<' in translation or '>' in translation:
                            target.text = f'<![CDATA[{translation}]]>'
                        else:
                            target.text = translation
            
            # Small delay to avoid rate limits
            time.sleep(0.5)
        
        # Save the result
        if inline:
            output_file = input_file
        else:
            output_file = f"{os.path.splitext(input_file)[0]}_translated.xlf"
        
        # Register namespace prefix
        ET.register_namespace('', 'urn:oasis:names:tc:xliff:document:1.2')
        
        # Write the file preserving CDATA sections and HTML entities
        def write_with_cdata(elem, file, encoding='utf-8'):
            def format_element(el):
                result = []
                tag = el.tag.split('}')[-1]  # Remove namespace
                
                # Start tag with attributes
                attrs = []
                # Add xmlns attribute for root element
                if tag == 'xliff':
                    attrs.append('xmlns="urn:oasis:names:tc:xliff:document:1.2"')
                # Add other attributes
                attrs.extend(f'{k}="{v}"' for k, v in sorted(el.attrib.items()))
                attrs_str = ' ' + ' '.join(attrs) if attrs else ''
                result.append(f'<{tag}{attrs_str}>')
                
                # Handle text content
                if el.text:
                    if el.tag.endswith('target'):
                        # For target elements, convert entities to HTML and wrap in CDATA if needed
                        from html import unescape
                        text = unescape(el.text)  # Convert entities to HTML
                        if '<' in text or '>' in text:
                            result.append(f'<![CDATA[{text}]]>')
                        else:
                            result.append(text)
                    else:
                        # For non-target elements, keep original text with entities
                        result.append(el.text)
                
                # Process children
                for child in el:
                    result.extend(format_element(child))
                    if child.tail:
                        result.append(child.tail)
                
                # End tag
                result.append(f'</{tag}>')
                return result
            
            # Write XML declaration
            file.write(f'<?xml version="1.0" encoding="utf-8"?>\n'.encode(encoding))
            
            # Write formatted content with minimal spacing
            content = ''.join(format_element(elem))
            file.write(content.encode(encoding))

        with open(output_file, 'wb') as f:
            write_with_cdata(root, f)
        print(f"Translations saved to: {output_file}")
            
    except Exception as e:
        print(f"Error processing file: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Translate untranslated strings in XLF files using OpenAI API")
    parser.add_argument("input_file", help="Path to the XLF file to translate")
    parser.add_argument("--language", "-l", help="Target language (e.g., es, fr, de). If not provided, will try to detect from filename")
    parser.add_argument("--inline", "-i", action="store_true", help="Edit file in-place instead of creating a new file")
    parser.add_argument("--force", "-f", action="store_true", help="Force translation of all strings, even if already translated")
    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        print(f"Error: File {args.input_file} not found")
        sys.exit(1)

    if not args.input_file.lower().endswith('.xlf'):
        print("Error: Input file must be an XLF file")
        sys.exit(1)

    process_xlf_file(args.input_file, args.language, args.inline, args.force)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nTranslation interrupted by user.")
        sys.exit(0)
