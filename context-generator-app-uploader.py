# -*- coding: utf-8 -*-
import streamlit as st
import os
import glob
import subprocess
# import sys # No longer needed unless used elsewhere
import shutil
import shlex
from pathlib import Path

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
def display_warning(message): st.toast(f"⚠️ Warning: {message}", icon="⚠️")
def display_info(message): st.toast(f"ℹ️ Info: {message}", icon="ℹ️")

def check_command(command_name):
    """Checks if a command exists in the system's PATH."""
    if shutil.which(command_name) is None:
        st.warning(f"'{command_name}' not found in PATH. Please install it and ensure it's accessible.", icon="⚠️")
        return False
    return True

def check_llama_parse_auth():
    """Checks if the LlamaParse configuration file exists."""
    if not os.path.exists(LLAMA_PARSE_CONFIG_FILE):
        st.error(f"**LlamaParse Not Authenticated:** Config file (`{LLAMA_PARSE_CONFIG_FILE}`) not found. "
                 f"Run `{LLAMA_PARSE_COMMAND} auth` in your terminal, enter your API key, then refresh this page.", icon="🔑")
        return False
    return True

def list_files(directory, pattern="*.*"):
    """Lists files in a directory matching a pattern, returning Path objects."""
    if not directory:
        # display_warning(f"Directory path is empty, cannot list files.") # Reduce noise maybe?
        return []
    dir_path = Path(directory)
    if not dir_path.is_dir():
        return []
    try:
        return sorted([f for f in dir_path.glob(pattern) if f.is_file()])
    except Exception as e:
        display_error(f"Error listing files in '{directory}': {e}")
        return []

def handle_upload(uploaded_files, target_directory):
    """Saves uploaded files to the target directory."""
    if not uploaded_files:
        return 0 # Return count of saved files
    if not target_directory:
        display_error("Target directory for upload is not set.")
        return 0

    saved_count = 0
    skipped_count = 0
    try:
        target_path = Path(target_directory)
        target_path.mkdir(parents=True, exist_ok=True) # Use pathlib for consistency

        for uploaded_file in uploaded_files:
            dest_path = target_path / uploaded_file.name
            if dest_path.exists():
                 display_warning(f"Overwriting existing file: '{uploaded_file.name}' in '{target_directory}'")
            try:
                with open(dest_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                saved_count += 1
            except Exception as e:
                display_error(f"Could not save '{uploaded_file.name}': {e}")
                skipped_count += 1

        if saved_count > 0:
            display_success(f"Successfully uploaded {saved_count} file(s) to '{target_directory}'.")
        if skipped_count > 0:
            display_error(f"Failed to upload {skipped_count} file(s).")
    except OSError as e:
        display_error(f"Could not create directory '{target_directory}': {e}")
    except Exception as e:
        display_error(f"An unexpected error occurred during upload: {e}")

    return saved_count # Return how many files were actually saved

def delete_file(filepath_str):
    """Deletes a specific file."""
    try:
        if not filepath_str:
            display_warning("Empty filepath provided for deletion.")
            return
        filepath = Path(filepath_str) # Work with Path object
        if filepath.is_file():
            filename = filepath.name
            filepath.unlink() # Use unlink for files
            display_success(f"Deleted '{filename}'. Refreshing list...")
            # Use st.experimental_rerun() to force refresh of the file list immediately
            st.experimental_rerun()
        else:
            display_warning(f"File not found, cannot delete: '{filepath_str}'")
    except OSError as e:
        display_error(f"Error deleting file '{filepath_str}': {e}")
    except Exception as e:
        display_error(f"Unexpected error deleting file '{filepath_str}': {e}")

# --- Core Processing Functions ---
def parse_pdfs(pdf_input_dir, parsed_output_dir):
    """Parses PDF files using LlamaParse CLI."""
    st.write(f"Parsing PDFs from: `{pdf_input_dir}` -> `{parsed_output_dir}`")
    if not check_command(LLAMA_PARSE_COMMAND): display_error(f"'{LLAMA_PARSE_COMMAND}' not found."); return False, 0, 0
    if not check_llama_parse_auth(): return False, 0, 0

    # Ensure input dir exists (using pathlib)
    pdf_input_path = Path(pdf_input_dir)
    if not pdf_input_path.is_dir():
        display_error(f"PDF Input Directory not found: '{pdf_input_dir}'")
        return False, 0, 0

    # Ensure output dir exists, clear if necessary (using pathlib)
    parsed_output_path = Path(parsed_output_dir)
    st.write(f"Preparing output directory: `{parsed_output_dir}`...")
    try:
        if parsed_output_path.exists():
            shutil.rmtree(parsed_output_path) # Clear previous results
        parsed_output_path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        display_error(f"Could not create/clear output directory '{parsed_output_dir}': {e}")
        return False, 0, 0

    try:
        pdf_files = list_files(pdf_input_dir, "*.pdf") # Already uses pathlib
    except Exception as e:
        display_error(f"Error finding PDFs in '{pdf_input_dir}': {e}")
        return False, 0, 0

    if not pdf_files:
        st.warning(f"No PDF files found in '{pdf_input_dir}'.", icon="ℹ️")
        return True, 0, 0 # No files is not an error state for processing

    st.write(f"Found {len(pdf_files)} PDF(s) to process.")
    progress_bar = st.progress(0)
    success_count, failure_count = 0, 0
    env = os.environ.copy()

    for i, pdf_path_obj in enumerate(pdf_files):
        pdf_file_str = str(pdf_path_obj) # Convert Path object to string for subprocess

        base_filename = pdf_path_obj.stem # Get filename without extension
        output_filename = f"{base_filename}.md"
        output_filepath = parsed_output_path / output_filename # Use pathlib for joining
        output_filepath_str = str(output_filepath)

        st.write(f"Processing '{pdf_path_obj.name}'...")

        try:
            command = [LLAMA_PARSE_COMMAND, "parse", pdf_file_str, "-o", output_filepath_str, "--format", "markdown"]
            # Basic check (subprocess handles more complex type issues)
            # isinstance check not strictly necessary as subprocess expects strings typically
            # if not all(isinstance(arg, (str, bytes, os.PathLike)) for arg in command):
            #      st.write(f"-> ERROR: Invalid argument types for command. Skipping '{pdf_path_obj.name}'.")
            #      failure_count += 1
            #      continue

            result = subprocess.run(command, capture_output=True, text=True, check=False, env=env, timeout=300) # 5 min timeout

            if result.returncode == 0:
                if output_filepath.exists():
                    success_count += 1
                    st.write(f"-> Parsed to '{output_filename}'")
                else:
                    st.write(f"-> WARN: Command succeeded but output file '{output_filename}' not found. Check LlamaParse logs/status.")
                    failure_count += 1
            else:
                st.write(f"-> ERROR: {LLAMA_PARSE_COMMAND} failed (code {result.returncode}) for '{pdf_path_obj.name}'.")
                failure_count += 1
                if result.stdout: st.text_area(f"{LLAMA_PARSE_COMMAND} Output", result.stdout.strip(), height=50, key=f"out_{pdf_path_obj.name}")
                if result.stderr: st.text_area(f"{LLAMA_PARSE_COMMAND} Error", result.stderr.strip(), height=50, key=f"err_{pdf_path_obj.name}")

        except FileNotFoundError:
            display_error(f"'{LLAMA_PARSE_COMMAND}' command not found. Cannot process PDFs.")
            return False, success_count, failure_count # Critical error, stop processing
        except subprocess.TimeoutExpired:
            st.write(f"-> ERROR: Timeout processing '{pdf_path_obj.name}'. It may be too large or complex.")
            failure_count += 1
        except Exception as e:
            st.write(f"-> ERROR: Unexpected error processing '{pdf_path_obj.name}': {e}")
            failure_count += 1

        progress_bar.progress((i + 1) / len(pdf_files))

    st.write(f"--- Parsing Summary --- Success: {success_count}, Failures: {failure_count}")
    if failure_count > 0:
        display_error(f"{failure_count} PDF(s) failed to parse.")
        return False, success_count, failure_count
    elif success_count > 0:
        display_success("PDF parsing completed successfully.")
        return True, success_count, failure_count
    else:
        # No successes, but also no failures reported (might happen if only warnings occurred or no PDFs found initially)
        if len(pdf_files) > 0 : # Only display if files were attempted
             display_info("PDF parsing finished, but no files were successfully parsed.")
        return True, success_count, failure_count # Technically didn't fail overall process


def combine_files_via_cli(directories_to_scan, output_filepath_str):
    """Combines text/markdown files from specified directories using files-to-prompt CLI."""
    st.write(f"Combining files via '{FILES_TO_PROMPT_COMMAND}' CLI...")
    if not check_command(FILES_TO_PROMPT_COMMAND): display_error(f"'{FILES_TO_PROMPT_COMMAND}' not found."); return False, None
    if not directories_to_scan: display_error("No input directories specified for combining."); return False, None

    valid_dirs = []
    for d_str in directories_to_scan:
        d_path = Path(d_str).resolve() # Use absolute paths
        if d_path.is_dir():
            valid_dirs.append(str(d_path)) # Keep as strings for shlex/subprocess
        else:
            st.warning(f"Input directory not found or not a directory, skipping: '{d_str}'")

    if not valid_dirs:
        display_error(f"No valid input directories found to combine.")
        return False, None

    # Ensure output directory exists (using pathlib)
    output_filepath = Path(output_filepath_str).resolve()
    output_dir = output_filepath.parent
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        display_error(f"Could not create output directory '{output_dir}' for context file: {e}")
        return False, None

    # Use shlex.quote for directory paths to handle spaces/special characters
    # Pass the resolved absolute path string to shlex.quote
    quoted_output_filepath = shlex.quote(str(output_filepath))
    command = [FILES_TO_PROMPT_COMMAND] + [shlex.quote(d) for d in valid_dirs] + ["--cxml", "-o", quoted_output_filepath]

    st.info(f"Combining directories: `{', '.join(valid_dirs)}`")
    st.write(f"Executing command: `{' '.join(command)}`") # Show the user the command being run

    try:
        # Set timeout (e.g., 5 minutes)
        result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=300)

        if result.returncode == 0:
            if output_filepath.exists():
                display_success(f"'{FILES_TO_PROMPT_COMMAND}' completed. Output written to '{output_filepath}'")
                try:
                    with open(output_filepath, "r", encoding="utf-8") as f:
                        file_content = f.read()
                    return True, file_content
                except IOError as e:
                    display_error(f"Successfully created context file, but could not read it back: '{output_filepath}': {e}")
                    return False, None # File created but unreadable is a failure state
            else:
                 display_error(f"'{FILES_TO_PROMPT_COMMAND}' command succeeded, but output file '{output_filepath}' was not created.")
                 return False, None

        else:
            display_error(f"'{FILES_TO_PROMPT_COMMAND}' failed (code {result.returncode}).")
            if result.stderr: st.text_area(f"{FILES_TO_PROMPT_COMMAND} Error Output", result.stderr.strip(), height=100, key="f2p_err")
            return False, None

    except FileNotFoundError:
        display_error(f"'{FILES_TO_PROMPT_COMMAND}' command not found. Cannot combine files.")
        return False, None
    except subprocess.TimeoutExpired:
        display_error(f"Timeout occurred while running '{FILES_TO_PROMPT_COMMAND}'. The process took too long.")
        return False, None
    except Exception as e:
        display_error(f"An unexpected error occurred running '{FILES_TO_PROMPT_COMMAND}': {e}")
        return False, None

# --- Load README Content ---
readme_content = f"Error: Could not load {README_FILE}"
try:
    script_dir = Path(__file__).parent
    readme_path = script_dir / README_FILE
    if readme_path.exists():
        with open(readme_path, "r", encoding="utf-8") as f:
            readme_content = f.read()
    else:
        # Try finding it relative to CWD if script_dir fails
        readme_path_cwd = Path.cwd() / README_FILE
        if readme_path_cwd.exists():
             with open(readme_path_cwd, "r", encoding="utf-8") as f:
                 readme_content = f.read()
        else:
            readme_content = f"Error: {README_FILE} not found in application directory ({script_dir}) or current working directory ({Path.cwd()})."

except Exception as e:
    readme_content = f"Error reading {README_FILE}: {e}"

# --- Streamlit App UI ---
st.set_page_config(layout="wide", page_title="Files-to-Prompt GUI")

with st.expander("README / Instructions", expanded=False):
    st.markdown(readme_content, unsafe_allow_html=False) # Keep unsafe_allow_html=False for security

st.title("📄 Files-to-Prompt Context Generator")
st.caption(f"Graphical interface for `{FILES_TO_PROMPT_COMMAND}` & `{LLAMA_PARSE_COMMAND}`.")
st.info(f"Ensure required tools are installed & `{LLAMA_PARSE_COMMAND}` is authenticated (run `{LLAMA_PARSE_COMMAND} auth` in terminal if needed). See README.", icon="ℹ️")

# --- Sidebar ---
with st.sidebar:
    st.header("⚙️ Configuration")
    st.subheader("Input Folders")
    # Use session state to preserve input values across reruns/tab switches
    # Initialize session state keys ONLY if they don't exist
    if 'pdf_dir' not in st.session_state: st.session_state.pdf_dir = os.path.abspath(DEFAULT_PDF_INPUT_DIR)
    if 'txt_dir' not in st.session_state: st.session_state.txt_dir = os.path.abspath(DEFAULT_TXT_INPUT_DIR)
    if 'out_file' not in st.session_state: st.session_state.out_file = DEFAULT_OUTPUT_FILENAME
    if 'out_loc' not in st.session_state: st.session_state.out_loc = os.path.abspath(".")

    # Widgets read directly from session state for their default/current value
    # Their value will automatically update session state on change
    st.text_input(
        "PDF Input Folder",
        value=st.session_state.pdf_dir, # Read from state
        key="pdf_dir", # Let widget manage this state key
        help="Absolute path to the folder containing PDF files to be parsed."
    )
    st.text_input(
        "TXT Input Folder",
        value=st.session_state.txt_dir, # Read from state
        key="txt_dir", # Let widget manage this state key
        help="Absolute path to the folder containing TXT/MD/etc. files to be combined. Parsed PDFs will be placed in a subfolder here."
    )

    st.subheader("Output Settings")
    # Define parsed PDF output dir based on the *current* TXT input dir state
    # Use os.path.join for cross-platform compatibility
    parsed_pdf_output_dir_abs = os.path.join(st.session_state.txt_dir, DEFAULT_PARSED_PDF_OUTPUT_SUBDIR)
    st.info(f"Parsed PDFs will be saved to:\n`{parsed_pdf_output_dir_abs}`\n(This folder will be cleared on parsing)")

    st.text_input(
        "Output Context Filename",
        value=st.session_state.out_file, # Read from state
        key="out_file", # Let widget manage this state key
        help="Filename for the final combined context file."
        )
    st.text_input(
        "Output File Location",
        value=st.session_state.out_loc, # Read from state
        key="out_loc", # Let widget manage this state key
        help="Directory where the final context file will be saved."
        )

    # Calculate final path based on current state values for display
    # Use os.path.join and os.path.abspath
    output_filepath_abs = os.path.abspath(os.path.join(st.session_state.out_loc, st.session_state.out_file))
    st.info(f"Final context file will be written to:\n`{output_filepath_abs}`")

    # --- NO LONGER NEEDED ---
    # The widgets update session state automatically.
    # Do not assign back to session state here.
    # --- REMOVED LINES ---

# --- Main Area with Tabs ---
tab1, tab2, tab3 = st.tabs(["🚀 Process Files", "📤 PDF Upload", "📝 Plaintext Upload"])

with tab1:
    st.header("🚀 Process Files")
    # Use absolute paths directly from session state
    current_pdf_dir = st.session_state.pdf_dir
    current_txt_dir = st.session_state.txt_dir
    # Calculate derived paths based on current state
    current_parsed_dir = os.path.join(current_txt_dir, DEFAULT_PARSED_PDF_OUTPUT_SUBDIR)
    current_output_file = os.path.abspath(os.path.join(st.session_state.out_loc, st.session_state.out_file))

    process_option = st.radio(
        "Select content to include:",
        ("TXT files only", "PDF files only", "Both PDF and TXT files"),
        index=2, # Default to Both
        key="proc_opt",
        help="Choose which types of files to process into the final context file. 'PDF files only' will first parse PDFs to Markdown, then combine only those Markdown files. 'Both' will parse PDFs and then combine the resulting Markdown files along with any files already in the TXT input folder."
    )
    st.write("---")

    if st.button("Generate Context File", key="generate_main", type="primary"):
        final_context_content = None
        directories_to_scan_for_combine = []
        parsing_step_ok = True # Track if the parsing step (if run) succeeded

        # --- Step 1: PDF Parsing (if selected) ---
        if process_option in ["PDF files only", "Both PDF and TXT files"]:
            st.subheader("Step 1: Parsing PDFs")
            parsing_step_ok, successes, failures = parse_pdfs(current_pdf_dir, current_parsed_dir)
            if not parsing_step_ok:
                 st.error("PDF parsing step failed. Check errors above. Cannot proceed with combining parsed PDFs.")
            elif successes == 0 and failures == 0:
                 # Check if source dir was actually empty
                 if not any(Path(current_pdf_dir).glob("*.pdf")):
                     st.info("No PDFs found in the input directory to parse.")
                 else: # PDFs existed but none succeeded
                     st.warning("PDFs were found but none were successfully parsed.")
                     if process_option == "PDF files only":
                         parsing_step_ok = False # Fail if this was the only source
            elif successes > 0:
                # Add parsed dir only if parsing succeeded and produced files
                if Path(current_parsed_dir).is_dir():
                     directories_to_scan_for_combine.append(current_parsed_dir)
                else:
                    # This shouldn't happen if parse_pdfs reported success, but check anyway
                    st.warning(f"Parsed PDF output directory '{current_parsed_dir}' not found after parsing success report. It will not be included.")
                    if process_option == "PDF files only":
                         parsing_step_ok = False

        # --- Step 2: Determine Directories for Combination ---
        # Proceed to combination step only if parsing (if performed) was OK OR if only TXT files are selected
        if parsing_step_ok or process_option == "TXT files only":
            st.subheader("Step 2: Combining Files")
            combination_step_possible = True # Track if we have valid dirs for this step

            # Add TXT dir if needed
            if process_option in ["TXT files only", "Both PDF and TXT files"]:
                txt_dir_path = Path(current_txt_dir)
                if not txt_dir_path.is_dir():
                    st.warning(f"TXT Input Folder not found or invalid: '{current_txt_dir}'. It will not be included in the combination.")
                    if process_option == "TXT files only":
                        combination_step_possible = False
                        st.error("TXT directory is invalid and 'TXT files only' was selected. Cannot proceed.")
                else:
                    # Add TXT dir if it's not already in the list (e.g. from parsed PDFs)
                    # and ensure it's not the parent of the parsed dir (avoid double counting)
                    parsed_dir_path = Path(current_parsed_dir)
                    is_parent_of_parsed = False
                    try:
                        # Check if parsed_dir_path is a direct or indirect child of txt_dir_path
                        # .relative_to() throws ValueError if it's not a subpath
                        parsed_dir_path.relative_to(txt_dir_path)
                        is_parent_of_parsed = True
                    except ValueError:
                        is_parent_of_parsed = False


                    if current_txt_dir not in directories_to_scan_for_combine and not is_parent_of_parsed:
                        directories_to_scan_for_combine.append(current_txt_dir)
                    elif is_parent_of_parsed and current_txt_dir != current_parsed_dir:
                         # Only warn if they are distinct but parent/child
                         st.warning(f"TXT directory '{current_txt_dir}' contains the parsed PDF output directory. Skipping the parent TXT directory in combination step to avoid potential duplicate content.")
                    # If txt_dir and parsed_dir are the same, it's already added, do nothing.


            # --- Step 3: Run Combination ---
            if not combination_step_possible:
                st.error("Cannot proceed with file combination due to invalid input directories.")
            elif not directories_to_scan_for_combine:
                 st.warning("No valid input directories found or specified to combine files from. Context file generation skipped.")
            else:
                 # Ensure paths passed are strings
                 dirs_as_strings = [str(d) for d in directories_to_scan_for_combine]
                 output_file_as_string = str(current_output_file)
                 combine_ok, combined_data = combine_files_via_cli(dirs_as_strings, output_file_as_string)
                 if combine_ok:
                     final_context_content = combined_data
                 else:
                     st.error("File combination step failed.")

        # --- Step 4: Display Output ---
        st.subheader("Step 3: Output Preview")
        if final_context_content:
            st.success(f"Context file generated/overwritten successfully at `{current_output_file}`.")
            # Use markdown language for potential XML/Markdown highlighting
            st.code(final_context_content, language="markdown", line_numbers=True)
        else:
            st.warning("Context file generation was not completed or failed. Check messages above.")

with tab2:
    st.header("📤 Manage PDF Files for Parsing")
    current_pdf_dir = st.session_state.pdf_dir # Get from session state
    st.write(f"**Target Directory:** `{current_pdf_dir}`")
    st.markdown("---")

    # Ensure directory exists for uploads and listing
    try:
        Path(current_pdf_dir).mkdir(parents=True, exist_ok=True)
    except OSError as e:
        st.error(f"Could not create PDF directory '{current_pdf_dir}': {e}. Uploads and listing may fail.")

    # Upload Section
    st.subheader("Upload New PDFs")
    uploaded_pdfs = st.file_uploader(
        "Select PDF files to upload:",
        type="pdf",
        accept_multiple_files=True,
        key="pdf_uploader" # Unique key for this uploader
    )
    if uploaded_pdfs:
        num_saved = handle_upload(uploaded_pdfs, current_pdf_dir)
        if num_saved > 0:
             # Rerun to show the newly uploaded files in the list below
             st.experimental_rerun()
        # Clear the uploader's internal list after processing
        # uploaded_pdfs = None # This might not be needed if rerun happens

    st.markdown("---")

    # File Listing and Deletion Section
    st.subheader("Existing PDF Files")
    if st.button("🔄 Refresh PDF List", key="refresh_pdfs"):
        st.experimental_rerun() # Explicit refresh button

    pdf_files_in_dir = list_files(current_pdf_dir, "*.pdf") # Returns list of Path objects

    if not pdf_files_in_dir:
        st.info(f"No PDF files found in `{current_pdf_dir}`.")
    else:
        st.write(f"Found {len(pdf_files_in_dir)} PDF file(s):")
        cols_per_row = 3
        # Create columns dynamically based on number of files to avoid empty columns
        num_cols = min(len(pdf_files_in_dir), cols_per_row)
        if num_cols > 0:
            cols = st.columns(num_cols)
            for i, file_path_obj in enumerate(pdf_files_in_dir):
                # file_path_str = str(file_path_obj) # Keep as Path object where possible
                filename = file_path_obj.name
                col_idx = i % num_cols
                with cols[col_idx]:
                    # Use an expander for potentially long filenames? Or just markdown
                    st.markdown(f"📄 `{filename}`")
                    # Add unique key including index and filename to prevent conflicts
                    if st.button(f"🗑️ Delete##PDF_{i}_{filename}", key=f"del_pdf_{i}_{filename}", help=f"Delete {filename}"):
                        delete_file(str(file_path_obj)) # Pass path string to delete_file
                        # Rerun is handled by delete_file function itself


with tab3:
    st.header("📝 Manage Plaintext Files for Combination")
    current_txt_dir = st.session_state.txt_dir # Get from session state
    current_parsed_subdir_name = DEFAULT_PARSED_PDF_OUTPUT_SUBDIR
    st.write(f"**Target Directory:** `{current_txt_dir}`")
    st.caption(f"Note: The parsed PDF output subfolder (`{current_parsed_subdir_name}`) within this directory is managed automatically by the 'Process Files' tab.")
    st.markdown("---")

    # Ensure directory exists for uploads and listing
    try:
        Path(current_txt_dir).mkdir(parents=True, exist_ok=True)
    except OSError as e:
        st.error(f"Could not create TXT directory '{current_txt_dir}': {e}. Uploads and listing may fail.")

    # Upload Section
    st.subheader("Upload New Text/Markdown/Code Files")
    allowed_types = ["txt", "md", "markdown", "json", "xml", "yaml", "yml", "py", "js", "html", "css", "csv", "tsv", "rst"]
    uploaded_txts = st.file_uploader(
        f"Select files ({', '.join(allowed_types)}) to upload:",
        type=allowed_types,
        accept_multiple_files=True,
        key="txt_uploader" # Unique key
    )
    if uploaded_txts:
        num_saved = handle_upload(uploaded_txts, current_txt_dir)
        if num_saved > 0:
            # Rerun to update list below
             st.experimental_rerun()
        # uploaded_txts = None # May not be needed

    st.markdown("---")

    # File Listing and Deletion Section
    st.subheader("Existing Files (excluding parsed PDF subfolder)")
    if st.button("🔄 Refresh Text File List", key="refresh_txts"):
        st.experimental_rerun() # Explicit refresh

    # List all files, then filter out the parsed PDF subdir and its contents if it exists within this dir
    all_files_in_dir = list_files(current_txt_dir, "*.*") # List everything first
    parsed_pdf_subdir_path = Path(current_txt_dir) / current_parsed_subdir_name

    txt_files_to_display = []
    for file_path_obj in all_files_in_dir:
        # Check if the file's path starts with the parsed subdirectory path string
        try:
            # Use relative_to to robustly check if it's inside the subdir
            file_path_obj.relative_to(parsed_pdf_subdir_path)
            # If the above line doesn't raise ValueError, it's inside the subdir, so skip it
        except ValueError:
            # It's not inside the parsed subdir, so include it
            txt_files_to_display.append(file_path_obj)
        except Exception as e:
            # Handle potential errors during path comparison, though unlikely
            st.warning(f"Could not compare path {file_path_obj} with {parsed_pdf_subdir_path}: {e}")


    if not txt_files_to_display:
        st.info(f"No user-added text/code/markdown files found directly in `{current_txt_dir}` (excluding the '{current_parsed_subdir_name}' folder).")
    else:
        st.write(f"Found {len(txt_files_to_display)} relevant file(s):")
        cols_per_row = 3
        num_cols = min(len(txt_files_to_display), cols_per_row)
        if num_cols > 0:
            cols = st.columns(num_cols)
            for i, file_path_obj in enumerate(txt_files_to_display):
                # file_path_str = str(file_path_obj)
                filename = file_path_obj.name
                col_idx = i % num_cols
                with cols[col_idx]:
                    st.markdown(f"📄 `{filename}`")
                    # Unique key including type prefix, index, and filename
                    if st.button(f"🗑️ Delete##TXT_{i}_{filename}", key=f"del_txt_{i}_{filename}", help=f"Delete {filename}"):
                        delete_file(str(file_path_obj))
                        # Rerun handled by delete_file

# --- Footer ---
st.markdown("---")
st.caption(f"Using: `{LLAMA_PARSE_COMMAND}` & `{FILES_TO_PROMPT_COMMAND}`. Ensure they are installed and configured.")