# -*- coding: utf-8 -*-
import streamlit as st
import os
import subprocess
import shutil
import shlex
from pathlib import Path

# --- Configuration ---
DEFAULT_PDF_INPUT_DIR = "pdfs_to_parse"
DEFAULT_TXT_INPUT_DIR = "txt_files"
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
        st.warning(f"'{command_name}' not found. Install & ensure accessible.", icon="⚠️")
        return False
    return True

def check_llama_parse_auth():
    """Checks if LlamaParse config file exists."""
    if not os.path.exists(LLAMA_PARSE_CONFIG_FILE):
        st.error(f"**LlamaParse Auth Missing:** Config (`{LLAMA_PARSE_CONFIG_FILE}`) missing. "
                 f"Run `{LLAMA_PARSE_COMMAND} auth` in terminal, enter key, refresh.", icon="🔑")
        return False
    return True

def list_files(directory, pattern="*.*"):
    """Lists files matching pattern, returns Path objects."""
    if not directory: return []
    dir_path = Path(directory)
    if not dir_path.is_dir(): return []
    try: return sorted([f for f in dir_path.glob(pattern) if f.is_file()])
    except Exception as e: display_error(f"List files error '{directory}': {e}"); return []

def handle_upload(uploaded_files, target_directory):
    """Saves uploaded files."""
    # ... (handle_upload logic remains the same) ...
    if not uploaded_files: return 0
    if not target_directory: display_error("Target upload dir not set."); return 0
    saved = 0; skipped = 0
    try:
        target_path = Path(target_directory); target_path.mkdir(parents=True, exist_ok=True)
        for up_file in uploaded_files:
            dest = target_path / up_file.name
            if dest.exists(): display_warning(f"Overwriting: '{up_file.name}'")
            try:
                with open(dest, "wb") as f: f.write(up_file.getbuffer())
                saved += 1
            except Exception as e: display_error(f"Save failed '{up_file.name}': {e}"); skipped += 1
        if saved > 0: display_success(f"Uploaded {saved} file(s). Use Refresh.")
        if skipped > 0: display_error(f"Failed {skipped} upload(s).")
    except OSError as e: display_error(f"Create dir error '{target_directory}': {e}")
    except Exception as e: display_error(f"Upload error: {e}")
    return saved


def delete_file(filepath_str):
    """Deletes file and reruns."""
    # ... (delete_file logic remains the same) ...
    try:
        if not filepath_str: display_warning("Empty path for deletion."); return
        fp = Path(filepath_str)
        if fp.is_file(): fn = fp.name; fp.unlink(); display_success(f"Deleted '{fn}'. Refreshing..."); st.rerun()
        else: display_warning(f"Not found: '{filepath_str}'")
    except OSError as e: display_error(f"Delete error '{filepath_str}': {e}")
    except Exception as e: display_error(f"Unexpected delete error: {e}")

def clear_directory(dir_path_str):
    """Removes and recreates a directory if it exists."""
    dir_path = Path(dir_path_str)
    cleared = False
    if dir_path.exists():
        try:
            shutil.rmtree(dir_path)
            dir_path.mkdir(parents=True, exist_ok=True) # Recreate immediately
            display_info(f"Cleared directory: '{dir_path_str}'")
            cleared = True
        except OSError as e:
            display_error(f"Failed to clear directory '{dir_path_str}': {e}")
            cleared = False
    else:
        # Directory doesn't exist, effectively cleared, maybe create it?
        try:
            dir_path.mkdir(parents=True, exist_ok=True) # Ensure it exists if needed later
            cleared = True # Treat non-existent as 'clear'
        except OSError as e:
             display_error(f"Failed to create non-existent dir '{dir_path_str}' while 'clearing': {e}")
             cleared = False
    return cleared


# --- Core Processing Functions ---
def parse_pdfs(pdf_input_dir, parsed_output_dir):
    """Parses PDF files using LlamaParse CLI. Clears output dir first."""
    # ... (parse_pdfs logic remains largely the same, including clearing output dir) ...
    st.write(f"Parsing PDFs from: `{pdf_input_dir}` -> `{parsed_output_dir}`")
    if not check_command(LLAMA_PARSE_COMMAND): display_error(f"'{LLAMA_PARSE_COMMAND}' not found."); return False, 0, 0
    if not check_llama_parse_auth(): return False, 0, 0
    pdf_in_path = Path(pdf_input_dir); parsed_out_path = Path(parsed_output_dir)
    if not pdf_in_path.is_dir(): display_error(f"PDF Input Dir not found: '{pdf_input_dir}'"); return False, 0, 0
    st.write(f"Preparing output directory: `{parsed_output_dir}`...")
    try:
        if parsed_out_path.exists(): shutil.rmtree(parsed_out_path) # Clear before parsing
        parsed_out_path.mkdir(parents=True, exist_ok=True)
    except OSError as e: display_error(f"Output dir error '{parsed_output_dir}': {e}"); return False, 0, 0
    pdfs = list_files(pdf_input_dir, "*.pdf")
    if not pdfs: st.warning(f"No PDF files found in '{pdf_input_dir}'.", icon="ℹ️"); return True, 0, 0
    st.write(f"Found {len(pdfs)} PDF(s) to process.")
    prog = st.progress(0); ok=0; fail=0; env = os.environ.copy()
    for i, pdf_obj in enumerate(pdfs):
        pdf_str = str(pdf_obj); base = pdf_obj.stem; out_fn = f"{base}.md"
        out_fp = parsed_out_path / out_fn; out_fp_str = str(out_fp)
        st.write(f"Processing '{pdf_obj.name}'...")
        try:
            cmd = [LLAMA_PARSE_COMMAND, "parse", pdf_str, "-o", out_fp_str, "--format", "markdown"]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env, timeout=300)
            if res.returncode == 0 and out_fp.exists(): ok += 1; st.write(f"-> Parsed to '{out_fn}'")
            elif res.returncode == 0: st.write("-> WARN: Cmd ok but output missing."); fail += 1
            else:
                fail += 1; st.write(f"-> ERROR: {LLAMA_PARSE_COMMAND} failed (code {res.returncode}) for '{pdf_obj.name}'.")
                with st.expander("Show Output/Error"):
                    if res.stdout: st.text_area("Out", res.stdout.strip(), height=100, key=f"out_{pdf_obj.name}")
                    if res.stderr: st.text_area("Err", res.stderr.strip(), height=100, key=f"err_{pdf_obj.name}")
        except FileNotFoundError: display_error(f"'{LLAMA_PARSE_COMMAND}' not found."); return False, ok, fail
        except subprocess.TimeoutExpired: st.write(f"-> ERROR: Timeout '{pdf_obj.name}'."); fail += 1
        except Exception as e: st.write(f"-> ERROR: Unexpected: {e}"); fail += 1
        finally: prog.progress((i + 1) / len(pdfs))
    st.write(f"--- Parsing Summary --- Success: {ok}, Failures: {fail}")
    if fail > 0: display_error(f"{fail} PDF(s) failed."); return False, ok, fail
    elif ok > 0: display_success("PDF parsing completed."); return True, ok, fail
    else:
        if len(pdfs) > 0: display_info("No PDFs parsed successfully.")
        return True, ok, fail

def combine_files_via_cli(dirs_to_scan, output_fp_str):
    """Combines files using files-to-prompt CLI (recursive)."""
    # ... (combine_files_via_cli logic remains the same) ...
    st.write(f"Combining files via '{FILES_TO_PROMPT_COMMAND}' CLI...")
    if not check_command(FILES_TO_PROMPT_COMMAND): display_error(f"'{FILES_TO_PROMPT_COMMAND}' not found."); return False, None
    if not dirs_to_scan: display_error("No input dirs specified."); return False, None
    valid = [str(d.resolve()) for d_str in dirs_to_scan if (d := Path(d_str)).is_dir() or st.warning(f"Skip invalid dir: '{d_str}'")]
    if not valid: display_error("No valid dirs found."); return False, None
    out_fp = Path(output_fp_str).resolve(); out_dir = out_fp.parent
    try: out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e: display_error(f"Output dir error '{out_dir}': {e}"); return False, None
    quoted_out_fp = shlex.quote(str(out_fp))
    cmd = [FILES_TO_PROMPT_COMMAND] + [shlex.quote(d) for d in valid] + ["--cxml", "-o", quoted_out_fp]
    st.info(f"Combining: `{', '.join(valid)}` (Recursive)") # Added recursive note
    st.write(f"Executing: `{' '.join(cmd)}`")
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=300)
        if res.returncode == 0 and out_fp.exists():
            display_success(f"Combined. Output: '{out_fp}'")
            try:
                with open(out_fp, "r", encoding="utf-8") as f: return True, f.read()
            except IOError as e: display_error(f"Read failed '{out_fp}': {e}"); return False, None
        elif res.returncode == 0: display_error(f"Cmd ok, output missing: '{out_fp}'."); return False, None
        else:
            display_error(f"'{FILES_TO_PROMPT_COMMAND}' failed (code {res.returncode}).")
            if res.stderr: st.text_area(f"{FILES_TO_PROMPT_COMMAND} Error", res.stderr.strip(), height=100, key="f2p_err")
            return False, None
    except FileNotFoundError: display_error(f"'{FILES_TO_PROMPT_COMMAND}' not found."); return False, None
    except subprocess.TimeoutExpired: display_error(f"Timeout running '{FILES_TO_PROMPT_COMMAND}'."); return False, None
    except Exception as e: display_error(f"Error running '{FILES_TO_PROMPT_COMMAND}': {e}"); return False, None

# --- Load README ---
# @st.cache_data
def load_readme():
    # ... (README loading logic remains the same) ...
    content = f"Error: Could not load {README_FILE}"; script_d = Path(__file__).parent
    p = script_d / README_FILE;
    if not p.exists(): p = Path.cwd() / README_FILE
    try:
        if p.exists(): content = p.read_text(encoding="utf-8")
        else: content = f"Error: {README_FILE} not found in {script_d} or {Path.cwd()}."
    except Exception as e: content = f"Error reading {README_FILE}: {e}"
    return content
readme_content = load_readme()

# --- Streamlit App UI ---
st.set_page_config(layout="wide", page_title="Files-to-Prompt GUI")
with st.expander("README / Instructions", expanded=False): st.markdown(readme_content, unsafe_allow_html=False)
st.title("📄 Files-to-Prompt Context Generator")
st.caption(f"Interface for `{FILES_TO_PROMPT_COMMAND}` & `{LLAMA_PARSE_COMMAND}`.")
# --- Initial Checks ---
did_llama = check_command(LLAMA_PARSE_COMMAND); did_f2p = check_command(FILES_TO_PROMPT_COMMAND); did_auth = False
if did_llama: did_auth = check_llama_parse_auth()
st.info(f"Tool checks: `{LLAMA_PARSE_COMMAND}`:{'✅' if did_llama else '❌'}, `{FILES_TO_PROMPT_COMMAND}`:{'✅' if did_f2p else '❌'}, LlamaParse Auth:{'✅' if did_auth else ('❔' if not did_llama else '❌')}", icon="ℹ️")

# --- Sidebar ---
with st.sidebar:
    st.header("⚙️ Configuration"); st.subheader("Input Folders")
    if 'pdf_dir' not in st.session_state: st.session_state.pdf_dir = os.path.abspath(DEFAULT_PDF_INPUT_DIR)
    if 'txt_dir' not in st.session_state: st.session_state.txt_dir = os.path.abspath(DEFAULT_TXT_INPUT_DIR)
    if 'out_file' not in st.session_state: st.session_state.out_file = "context_prompt_output.txt"
    if 'out_loc' not in st.session_state: st.session_state.out_loc = os.path.abspath(".")
    st.text_input("PDF Input Folder", value=st.session_state.pdf_dir, key="pdf_dir", help="Folder for PDFs.")
    st.text_input("TXT Input Folder", value=st.session_state.txt_dir, key="txt_dir", help="Folder for TXT/MD files.")
    st.subheader("Output Settings")
    parsed_pdf_dir = os.path.join(st.session_state.txt_dir, DEFAULT_PARSED_PDF_OUTPUT_SUBDIR)
    st.info(f"Parsed PDFs save to:\n`{parsed_pdf_dir}`\n(Cleared before parsing)")
    st.text_input("Output Context Filename", value=st.session_state.out_file, key="out_file", help="Output filename.")
    st.text_input("Output File Location", value=st.session_state.out_loc, key="out_loc", help="Output directory.")
    final_out_path = os.path.abspath(os.path.join(st.session_state.out_loc, st.session_state.out_file))
    st.info(f"Final context file:\n`{final_out_path}`")

# --- Main Area with Tabs ---
tab1, tab2, tab3 = st.tabs(["🚀 Process Files", "📤 PDF Upload", "📝 Plaintext Upload"])

# --- Tab 1: Process Files ---
with tab1:
    st.header("🚀 Process Files")
    pdf_d = st.session_state.pdf_dir; txt_d = st.session_state.txt_dir
    parsed_d = os.path.join(txt_d, DEFAULT_PARSED_PDF_OUTPUT_SUBDIR)
    out_f = os.path.abspath(os.path.join(st.session_state.out_loc, st.session_state.out_file))
    opt = st.radio("Include:", ("TXT only", "PDF only", "Both"), index=2, key="proc_opt", help="Sources.")
    st.write("---")

    if st.button("Generate Context File", key="generate_main", type="primary"):
        ctx_content = None; dirs_to_combine = []; parse_ok = True; pdf_successes = 0
        step_ok = True # Flag to control proceeding to combination

        # --- Step 1: PDF Parsing (if needed) ---
        if opt in ["PDF only", "Both"]:
            st.subheader("Step 1: Parsing PDFs")
            # parse_pdfs clears parsed_d before running
            parse_ok, pdf_successes, _ = parse_pdfs(pdf_d, parsed_d)
            if not parse_ok:
                st.error("PDF parsing step failed. Cannot reliably use parsed PDFs.")
                # If PDF only was selected, we must stop.
                if opt == "PDF only":
                    step_ok = False
                    st.stop()
            elif pdf_successes == 0 and opt == "PDF only":
                 st.warning("No PDFs were successfully parsed, and 'PDF only' was selected.")
                 step_ok = False # Don't proceed to combine if PDF only and none parsed

        # --- Step 2: Determine Directories & Pre-actions ---
        if step_ok:
            st.subheader("Step 2: Preparing for Combination")
            target_dir = None # The single directory to pass to files-to-prompt

            if opt == "Both":
                txt_p = Path(txt_d)
                if txt_p.is_dir():
                    target_dir = txt_d # Target parent dir, recursion includes parsed subfolder
                    st.write(f"Targeting TXT directory (recursive): `{target_dir}`")
                else:
                    st.error(f"TXT directory invalid ('{txt_d}') but required for 'Both' option.")
                    step_ok = False

            elif opt == "PDF only":
                parsed_p = Path(parsed_d)
                # Check if parsing ran, was ok (not strictly needed if success>0), produced files, and dir exists
                if pdf_successes > 0 and parsed_p.is_dir():
                    target_dir = parsed_d # Target only the subfolder with parsed files
                    st.write(f"Targeting Parsed PDF directory: `{target_dir}`")
                else:
                    st.warning("No successfully parsed PDFs found or directory missing. Cannot combine for 'PDF only'.")
                    step_ok = False

            elif opt == "TXT only":
                txt_p = Path(txt_d)
                if txt_p.is_dir():
                    st.write("Clearing parsed PDF directory (if it exists) for 'TXT only' mode...")
                    # Clear the parsed subfolder *before* targeting the parent
                    if clear_directory(parsed_d):
                        target_dir = txt_d # Target parent dir, recursion skips empty/non-existent parsed subfolder
                        st.write(f"Targeting TXT directory (recursive, parsed subdir cleared): `{target_dir}`")
                    else:
                        st.error("Failed to clear parsed PDF directory. Cannot reliably proceed with 'TXT only'.")
                        step_ok = False
                else:
                    st.error(f"TXT directory invalid ('{txt_d}') and required for 'TXT only' option.")
                    step_ok = False

            # --- Step 3: Run Combination ---
            if step_ok and target_dir:
                st.subheader("Step 3: Combining Files")
                # Pass only the single target directory
                combine_status, combined_data = combine_files_via_cli([str(target_dir)], str(out_f))
                if combine_status: ctx_content = combined_data
                else: st.error("Combination step failed.")
            elif step_ok and not target_dir:
                 st.warning("No target directory determined for combination.")


        # --- Step 4: Display Output ---
        st.subheader("Step 4: Output Preview")
        if ctx_content:
            st.success(f"Context generated: `{out_f}`.")
            st.code(ctx_content, language="markdown", line_numbers=True)
        else:
            st.warning("Context generation incomplete or failed.")

# --- Tab 2: PDF Upload ---
# ... (Tab 2 logic remains the same) ...
with tab2:
    st.header("📤 Manage PDF Files"); pdf_dir = st.session_state.pdf_dir
    st.write(f"**Target:** `{pdf_dir}`"); st.markdown("---")
    try: Path(pdf_dir).mkdir(parents=True, exist_ok=True)
    except OSError as e: st.error(f"Create PDF dir error: {e}.")
    st.subheader("Upload PDFs")
    up_pdfs = st.file_uploader("Select PDF files:", type="pdf", accept_multiple_files=True, key="pdf_uploader")
    if up_pdfs: handle_upload(up_pdfs, pdf_dir) # No rerun
    st.markdown("---"); st.subheader("Existing PDFs")
    if st.button("🔄 Refresh", key="refresh_pdfs"): pass # Natural rerun refreshes list
    pdf_files = list_files(pdf_dir, "*.pdf")
    if not pdf_files: st.info(f"No PDFs found in `{pdf_dir}`.")
    else:
        st.write(f"{len(pdf_files)} PDF(s):")
        for i, f_obj in enumerate(pdf_files):
            c1, c2 = st.columns([5, 1])
            with c1: st.markdown(f"📄 `{f_obj.name}`", unsafe_allow_html=False)
            with c2:
                if st.button("🗑️", key=f"del_pdf_{i}_{f_obj.name}", help=f"Delete {f_obj.name}"):
                    delete_file(str(f_obj)) # delete_file handles rerun
            st.divider()


# --- Tab 3: Plaintext Upload ---
# ... (Tab 3 logic remains the same) ...
with tab3:
    st.header("📝 Manage Plaintext Files"); txt_dir = st.session_state.txt_dir
    parsed_sub = DEFAULT_PARSED_PDF_OUTPUT_SUBDIR
    st.write(f"**Target:** `{txt_dir}`"); st.caption(f"Note: Subfolder (`{parsed_sub}`) managed automatically.")
    st.markdown("---")
    try: Path(txt_dir).mkdir(parents=True, exist_ok=True)
    except OSError as e: st.error(f"Create TXT dir error: {e}.")
    st.subheader("Upload Text/Code/MD Files")
    types = ["txt", "md", "markdown", "json", "xml", "yaml", "yml", "py", "js", "html", "css", "csv", "tsv", "rst"]
    up_txts = st.file_uploader(f"Select files ({', '.join(types)}):", type=types, accept_multiple_files=True, key="txt_uploader")
    if up_txts: handle_upload(up_txts, txt_dir) # No rerun
    st.markdown("---"); st.subheader("Existing Files (excluding parsed subfolder)")
    if st.button("🔄 Refresh", key="refresh_txts"): pass # Natural rerun
    all_f = list_files(txt_dir, "*.*"); parsed_p = Path(txt_dir) / parsed_sub
    txt_disp = [f for f in all_f if not str(f).startswith(str(parsed_p) + os.sep)]
    if not txt_disp: st.info(f"No user-added files found directly in `{txt_dir}`.")
    else:
        st.write(f"{len(txt_disp)} file(s):")
        for i, f_obj in enumerate(txt_disp):
            c1, c2 = st.columns([5, 1])
            with c1: st.markdown(f"📄 `{f_obj.name}`", unsafe_allow_html=False)
            with c2:
                if st.button("🗑️", key=f"del_txt_{i}_{f_obj.name}", help=f"Delete {f_obj.name}"):
                    delete_file(str(f_obj)) # delete_file handles rerun
            st.divider()

# --- Footer ---
st.markdown("---")
st.caption(f"Using: `{LLAMA_PARSE_COMMAND}` & `{FILES_TO_PROMPT_COMMAND}`.")