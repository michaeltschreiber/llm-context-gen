import streamlit as st
import os
import glob
import subprocess
import sys
import shutil
import shlex

# --- Configuration ---
DEFAULT_PDF_INPUT_DIR = "pdfs_to_parse"
DEFAULT_TXT_INPUT_DIR = "txt_files"
DEFAULT_OUTPUT_FILENAME = "promptgen_cxml.txt"
DEFAULT_PARSED_PDF_OUTPUT_SUBDIR = "parsed_pdfs_streamlit"
LLAMA_PARSE_COMMAND = "llama-parse"
FILES_TO_PROMPT_COMMAND = "files-to-prompt"
LLAMA_PARSE_CONFIG_FILE = os.path.expanduser("~/.llama-parse/config.json")
README_FILE = "README.md"

# --- Helper Functions ---
def display_error(message): st.toast(f"❌ Error: {message}", icon="❌")
def display_success(message): st.toast(f"✅ Success: {message}", icon="✅")

def check_command(command_name):
    if shutil.which(command_name) is None:
        st.warning(f"'{command_name}' not found in PATH. Install & ensure accessible.", icon="⚠️")
        return False
    return True

def check_llama_parse_auth():
    if not os.path.exists(LLAMA_PARSE_CONFIG_FILE):
        st.error(f"**LlamaParse Not Authenticated:** Config file (`{LLAMA_PARSE_CONFIG_FILE}`) not found. "
                 f"Run `llama-parse auth` in terminal, enter key, then retry.", icon="🔑")
        return False
    return True

# --- Core Functions ---
# parse_pdfs, combine_files_via_cli (remain the same as previous version)
def parse_pdfs(pdf_input_dir, parsed_output_dir):
    st.write(f"Parsing PDFs from: `{pdf_input_dir}` -> `{parsed_output_dir}`")
    if not check_command(LLAMA_PARSE_COMMAND): display_error(f"'{LLAMA_PARSE_COMMAND}' not found."); return False, 0, 0
    if not check_llama_parse_auth(): return False, 0, 0

    try: os.makedirs(parsed_output_dir, exist_ok=True)
    except OSError as e: display_error(f"Could not create output dir '{parsed_output_dir}': {e}"); return False, 0, 0
    try: pdf_files = glob.glob(os.path.join(pdf_input_dir, "*.pdf"))
    except Exception as e: display_error(f"Error finding PDFs in '{pdf_input_dir}': {e}"); return False, 0, 0

    if not pdf_files: st.warning(f"No PDF files found in '{pdf_input_dir}'.", icon="ℹ️"); return True, 0, 0

    st.write(f"Found {len(pdf_files)} PDF(s) to process.")
    progress_bar = st.progress(0)
    success_count, failure_count = 0, 0
    env = os.environ.copy()

    st.write(f"Clearing existing parsed files in `{parsed_output_dir}`...")
    try:
        if os.path.exists(parsed_output_dir): shutil.rmtree(parsed_output_dir)
        os.makedirs(parsed_output_dir)
    except Exception as e: display_error(f"Could not clear old parsed files directory: {e}")

    for i, pdf_file in enumerate(pdf_files):
        if pdf_file is None: st.write("-> ERROR: Invalid file path. Skipping."); failure_count += 1; continue
        st.write(f"Processing '{os.path.basename(pdf_file)}'...")
        base_filename = os.path.splitext(os.path.basename(pdf_file))[0]
        output_filename, output_filepath = f"{base_filename}.md", os.path.join(parsed_output_dir, f"{base_filename}.md")
        try:
            command = [LLAMA_PARSE_COMMAND, "parse", pdf_file, "-o", output_filepath, "--format", "markdown"]
            if not all(isinstance(arg, (str, bytes, os.PathLike)) for arg in command):
                 st.write(f"-> ERROR: Invalid args for '{os.path.basename(pdf_file)}'. Skipping."); failure_count += 1; continue
            result = subprocess.run(command, capture_output=True, text=True, check=False, env=env, timeout=300)
            if result.returncode == 0:
                 if os.path.exists(output_filepath): success_count += 1; st.write(f"-> Parsed to '{output_filename}'")
                 else: st.write(f"-> WARN: Cmd success but output '{output_filename}' not found.")
            else:
                st.write(f"-> ERROR: {LLAMA_PARSE_COMMAND} failed (code {result.returncode})."); failure_count += 1
                if result.stdout: st.text_area(f"{LLAMA_PARSE_COMMAND} Output", result.stdout, height=50)
                if result.stderr: st.text_area(f"{LLAMA_PARSE_COMMAND} Error", result.stderr, height=50)
        except FileNotFoundError: display_error(f"'{LLAMA_PARSE_COMMAND}' not found."); return False, success_count, failure_count
        except subprocess.TimeoutExpired: st.write(f"-> ERROR: Timeout processing '{os.path.basename(pdf_file)}'."); failure_count += 1
        except TypeError as te: st.write(f"-> ERROR: TypeError processing '{os.path.basename(pdf_file)}': {te}."); failure_count += 1
        except Exception as e: st.write(f"-> ERROR: Unexpected error processing '{os.path.basename(pdf_file)}': {e}"); failure_count += 1
        progress_bar.progress((i + 1) / len(pdf_files))

    st.write(f"--- Parsing Summary --- Success: {success_count}, Fail: {failure_count}");
    if failure_count > 0: display_error(f"{failure_count} PDF(s) failed."); return False, success_count, failure_count
    else: display_success("PDF parsing completed."); return True, success_count, failure_count

def combine_files_via_cli(directories_to_scan, output_filepath):
    st.write(f"Combining files via '{FILES_TO_PROMPT_COMMAND}' CLI...")
    if not check_command(FILES_TO_PROMPT_COMMAND): display_error(f"'{FILES_TO_PROMPT_COMMAND}' not found."); return False, None
    if not directories_to_scan: display_error("No input directories for combining."); return False, None
    valid_dirs = [d for d in directories_to_scan if os.path.isdir(d)]
    if not valid_dirs: display_error(f"Input directories not found: {directories_to_scan}"); return False, None
    try: os.makedirs(os.path.dirname(output_filepath), exist_ok=True)
    except OSError as e: display_error(f"Could not create output dir for '{output_filepath}': {e}"); return False, None

    command = [FILES_TO_PROMPT_COMMAND] + [shlex.quote(d) for d in valid_dirs] + ["--cxml", "-o", shlex.quote(output_filepath)]
    st.info(f"Combine dirs passed to CLI: `{directories_to_scan}`")
    st.write(f"Command: `{' '.join(command)}`")
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=300)
        if result.returncode == 0:
            # If overwrite is intended, we don't need to check if file exists before writing,
            # as the '-o' flag handles overwriting.
            display_success(f"'{FILES_TO_PROMPT_COMMAND}' completed. Output: '{output_filepath}'")
            try:
                with open(output_filepath, "r", encoding="utf-8") as f: file_content = f.read()
                return True, file_content
            except IOError as e: display_error(f"Could not read output file '{output_filepath}': {e}"); return False, None
        else:
            display_error(f"'{FILES_TO_PROMPT_COMMAND}' failed (code {result.returncode}).")
            if result.stderr: st.text_area(f"{FILES_TO_PROMPT_COMMAND} Error", result.stderr, height=100)
            return False, None
    except FileNotFoundError: display_error(f"'{FILES_TO_PROMPT_COMMAND}' not found."); return False, None
    except subprocess.TimeoutExpired: display_error(f"Timeout running '{FILES_TO_PROMPT_COMMAND}'."); return False, None
    except Exception as e: display_error(f"Error running '{FILES_TO_PROMPT_COMMAND}': {e}"); return False, None


# --- Load README Content ---
readme_content = f"Error: Could not load {README_FILE}"
try:
    script_dir = os.path.dirname(__file__)
    readme_path = os.path.join(script_dir, README_FILE)
    with open(readme_path, "r", encoding="utf-8") as f:
        readme_content = f.read()
except FileNotFoundError:
    readme_content = f"Error: {README_FILE} not found in application directory ({script_dir})."
except Exception as e:
    readme_content = f"Error reading {README_FILE}: {e}"


# --- Streamlit App UI ---
st.set_page_config(layout="wide")

with st.expander("README / Instructions", expanded=False):
    st.markdown(readme_content, unsafe_allow_html=False)

st.title("📄 Files-to-Prompt Context Generator")
st.caption(f"Uses `{FILES_TO_PROMPT_COMMAND}` & `{LLAMA_PARSE_COMMAND}`.")
st.info(f"Ensure tools are installed & `{LLAMA_PARSE_COMMAND}` is authenticated (`llama-parse auth`). See README.", icon="ℹ️")

# --- Sidebar ---
with st.sidebar:
    st.header("⚙️ Configuration")
    st.subheader("Input Folders")
    pdf_input_dir = st.text_input("PDF Input Folder", DEFAULT_PDF_INPUT_DIR, key="pdf_dir")
    txt_input_dir = st.text_input("TXT Input Folder", DEFAULT_TXT_INPUT_DIR, key="txt_dir")
    st.subheader("Output Settings")
    parsed_pdf_output_dir = os.path.join(txt_input_dir, DEFAULT_PARSED_PDF_OUTPUT_SUBDIR)
    st.info(f"Parsed PDFs save to: `{parsed_pdf_output_dir}`")
    output_filename_input = st.text_input("Output Context Filename", DEFAULT_OUTPUT_FILENAME, key="out_file")
    output_location_input = st.text_input("Output File Location", ".", key="out_loc")
    output_filepath = os.path.abspath(os.path.join(output_location_input, output_filename_input))
    st.info(f"Final context file: `{output_filepath}`")

# --- Main Area ---
st.header("🚀 Processing Options")
process_option = st.radio("Select content:", ("TXT files only", "PDF files only", "Both PDF and TXT files"), index=2, key="proc_opt")
st.write("---")

# REMOVED Overwrite Confirmation Logic

# --- Main Processing Block ---
# Always proceed when button is clicked
if st.button("Generate Context File", key="generate_main"):
    final_context_content = None
    directories_to_scan = []
    parsing_ok = True

    # PDF Parsing
    if process_option in ["PDF files only", "Both PDF and TXT files"]:
        if not pdf_input_dir or not os.path.isdir(pdf_input_dir): st.error(f"PDF Input Folder not found: '{pdf_input_dir}'"); parsing_ok = False
        else:
            parsing_ok, _, failures = parse_pdfs(pdf_input_dir, parsed_pdf_output_dir) # Clears old files inside
            if parsing_ok and failures == 0:
                if process_option == "PDF files only": directories_to_scan.append(os.path.abspath(parsed_pdf_output_dir))
            elif not parsing_ok or failures > 0: parsing_ok = False

    # Determine Dirs for Combination
    if parsing_ok:
        if process_option in ["TXT files only", "Both PDF and TXT files"]:
            if not txt_input_dir or not os.path.isdir(txt_input_dir): st.error(f"TXT Input Folder not found: '{txt_input_dir}'"); parsing_ok = False
            else:
                abs_txt_dir = os.path.abspath(txt_input_dir)
                if abs_txt_dir not in directories_to_scan: directories_to_scan.append(abs_txt_dir)

        # Combine Files
        if parsing_ok:
            if not directories_to_scan: st.warning("No input directories found for combining.")
            else:
                # combine_files_via_cli will overwrite output file via '-o' flag
                combine_ok, combined_data = combine_files_via_cli(directories_to_scan, output_filepath)
                if combine_ok: final_context_content = combined_data

    # Display Output
    st.header("📝 Output Preview (Claude XML Format)")
    if final_context_content:
        st.success(f"Context file generated/overwritten at `{output_filepath}`.")
        st.code(final_context_content, language="markdown", line_numbers=True)
    else: st.warning("Context file generation not completed or failed.")

# --- Footer ---
st.markdown("---")
st.caption(f"App uses: {LLAMA_PARSE_COMMAND} & {FILES_TO_PROMPT_COMMAND}")