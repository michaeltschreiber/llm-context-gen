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
    # ... (remains the same) ...
    if shutil.which(command_name) is None:
        st.warning(f"'{command_name}' not found. Install & ensure accessible.", icon="⚠️")
        return False
    return True

def check_llama_parse_auth():
    """Checks if LlamaParse config file exists."""
    # ... (remains the same) ...
    if not os.path.exists(LLAMA_PARSE_CONFIG_FILE):
        st.error(f"**LlamaParse Auth Missing:** Config (`{LLAMA_PARSE_CONFIG_FILE}`) missing. "
                 f"Run `{LLAMA_PARSE_COMMAND} auth` in terminal, enter key, refresh.", icon="🔑")
        return False
    return True

def list_files(directory, pattern="*.*"):
    """Lists files matching pattern, returns Path objects."""
    # ... (remains the same) ...
    if not directory: return []
    dir_path = Path(directory)
    # Check if dir exists before trying to list (avoid error toast for non-existent)
    if not dir_path.is_dir(): return []
    try: return sorted([f for f in dir_path.glob(pattern) if f.is_file()])
    except Exception as e: display_error(f"List files error '{directory}': {e}"); return []

def handle_upload(uploaded_files, target_directory):
    """Saves uploaded files."""
    # ... (remains the same - already creates target if needed) ...
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
        if saved > 0: display_success(f"Processed {saved} uploaded file(s).") # Message changed slightly
        if skipped > 0: display_error(f"Failed {skipped} upload(s).")
    except OSError as e: display_error(f"Create dir error '{target_directory}': {e}")
    except Exception as e: display_error(f"Upload error: {e}")
    return saved

def delete_file(filepath_str):
    """Deletes file and reruns."""
    # ... (remains the same) ...
    try:
        if not filepath_str: display_warning("Empty path for deletion."); return
        fp = Path(filepath_str)
        if fp.is_file(): fn = fp.name; fp.unlink(); display_success(f"Deleted '{fn}'. Refreshing..."); st.rerun()
        else: display_warning(f"Not found: '{filepath_str}'")
    except OSError as e: display_error(f"Delete error '{filepath_str}': {e}")
    except Exception as e: display_error(f"Unexpected delete error: {e}")

def clear_directory(dir_path_str):
    """Removes and recreates a directory if it exists."""
    # ... (remains the same - already creates dir if needed) ...
    dir_path = Path(dir_path_str); cleared = False
    if dir_path.exists():
        try:
            shutil.rmtree(dir_path); dir_path.mkdir(parents=True, exist_ok=True)
            display_info(f"Cleared directory: '{dir_path_str}'"); cleared = True
        except OSError as e: display_error(f"Failed to clear dir '{dir_path_str}': {e}"); cleared = False
    else:
        try: dir_path.mkdir(parents=True, exist_ok=True); cleared = True
        except OSError as e: display_error(f"Failed create non-existent dir '{dir_path_str}': {e}"); cleared = False
    return cleared

# --- Core Processing Functions ---
def parse_pdfs(pdf_input_dir, parsed_output_dir):
    """Parses PDF files using LlamaParse CLI. Clears output dir first."""
    # ... (remains the same - already ensures input/output dirs) ...
    st.write(f"Parsing PDFs from: `{pdf_input_dir}` -> `{parsed_output_dir}`")
    if not check_command(LLAMA_PARSE_COMMAND): display_error(f"'{LLAMA_PARSE_COMMAND}' not found."); return False, 0, 0
    if not check_llama_parse_auth(): return False, 0, 0
    pdf_in_path=Path(pdf_input_dir); parsed_out_path=Path(parsed_output_dir)
    # Input dir existence check is crucial before listing/parsing
    if not pdf_in_path.is_dir(): display_error(f"PDF Input Dir not found: '{pdf_input_dir}'"); return False, 0, 0
    st.write(f"Preparing output directory: `{parsed_output_dir}`...")
    try: # Clear and create output dir
        if parsed_out_path.exists(): shutil.rmtree(parsed_out_path)
        parsed_out_path.mkdir(parents=True, exist_ok=True)
    except OSError as e: display_error(f"Output dir error '{parsed_output_dir}': {e}"); return False, 0, 0
    pdfs = list_files(pdf_input_dir, "*.pdf") # Use list_files which handles non-existent dir
    if not pdfs: st.warning(f"No PDF files found in '{pdf_input_dir}'.", icon="ℹ️"); return True, 0, 0
    st.write(f"Found {len(pdfs)} PDF(s) to process.")
    prog = st.progress(0); ok=0; fail=0; env = os.environ.copy()
    for i, pdf_obj in enumerate(pdfs):
        pdf_str=str(pdf_obj); base=pdf_obj.stem; out_fn=f"{base}.md"; out_fp=parsed_out_path/out_fn; out_fp_str=str(out_fp)
        st.write(f"Processing '{pdf_obj.name}'...")
        try:
            cmd=[LLAMA_PARSE_COMMAND, "parse", pdf_str, "-o", out_fp_str, "--format", "markdown"]
            res=subprocess.run(cmd, capture_output=True, text=True, check=False, env=env, timeout=300)
            if res.returncode == 0 and out_fp.exists(): ok+=1; st.write(f"-> Parsed to '{out_fn}'")
            elif res.returncode == 0: st.write("-> WARN: Cmd ok but output missing."); fail+=1
            else:
                fail+=1; st.write(f"-> ERROR: {LLAMA_PARSE_COMMAND} failed (code {res.returncode}) for '{pdf_obj.name}'.")
                with st.expander("Show Output/Error"):
                    if res.stdout: st.text_area("Out", res.stdout.strip(), height=100, key=f"out_{pdf_obj.name}")
                    if res.stderr: st.text_area("Err", res.stderr.strip(), height=100, key=f"err_{pdf_obj.name}")
        except FileNotFoundError: display_error(f"'{LLAMA_PARSE_COMMAND}' not found."); return False, ok, fail
        except subprocess.TimeoutExpired: st.write(f"-> ERROR: Timeout '{pdf_obj.name}'."); fail+=1
        except Exception as e: st.write(f"-> ERROR: Unexpected: {e}"); fail+=1
        finally: prog.progress((i + 1) / len(pdfs))
    st.write(f"--- Parsing Summary --- Success: {ok}, Failures: {fail}")
    if fail > 0: display_error(f"{fail} PDF(s) failed."); return False, ok, fail
    elif ok > 0: display_success("PDF parsing completed."); return True, ok, fail
    else:
        if len(pdfs) > 0: display_info("No PDFs parsed successfully.")
        return True, ok, fail

def combine_files_via_cli(dirs_to_scan, output_fp_str):
    """Combines files using files-to-prompt CLI (recursive)."""
    # ... (remains the same - already ensures output dir) ...
    st.write(f"Combining files via '{FILES_TO_PROMPT_COMMAND}' CLI...")
    if not check_command(FILES_TO_PROMPT_COMMAND): display_error(f"'{FILES_TO_PROMPT_COMMAND}' not found."); return False, None
    if not dirs_to_scan: display_error("No input dirs specified."); return False, None
    # Filter for valid directories *before* resolving, handle potential errors during check
    valid_dirs_resolved = []
    for d_str in dirs_to_scan:
        try:
            d_path = Path(d_str)
            if d_path.is_dir():
                valid_dirs_resolved.append(str(d_path.resolve()))
            else:
                 st.warning(f"Skip invalid dir: '{d_str}'")
        except Exception as e:
             st.warning(f"Error checking dir '{d_str}': {e}")

    if not valid_dirs_resolved: display_error("No valid dirs found."); return False, None

    out_fp=Path(output_fp_str).resolve(); out_dir=out_fp.parent
    try: out_dir.mkdir(parents=True, exist_ok=True) # Ensure output dir exists
    except OSError as e: display_error(f"Output dir error '{out_dir}': {e}"); return False, None

    quoted_out_fp=shlex.quote(str(out_fp))
    cmd=[FILES_TO_PROMPT_COMMAND] + [shlex.quote(d) for d in valid_dirs_resolved] + ["--cxml", "-o", quoted_out_fp]
    st.info(f"Combining: `{', '.join(valid_dirs_resolved)}` (Recursive)"); st.write(f"Executing: `{' '.join(cmd)}`")
    try:
        res=subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=300)
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
    # ... (remains the same) ...
    content = f"Error loading {README_FILE}"; script_d = Path(__file__).parent; p = script_d / README_FILE
    if not p.exists(): p = Path.cwd() / README_FILE
    try:
        if p.exists(): content = p.read_text(encoding="utf-8")
        else: content = f"Error: {README_FILE} not found in {script_d} or {Path.cwd()}."
    except Exception as e: content = f"Error reading {README_FILE}: {e}"
    return content
readme_content = load_readme()

# --- Upload Callbacks ---
# ... (callbacks remain the same) ...
def process_pdf_upload():
    uploaded_files = st.session_state.get("pdf_uploader")
    pdf_dir = st.session_state.get("pdf_dir")
    if uploaded_files and pdf_dir: handle_upload(uploaded_files, pdf_dir)

def process_txt_upload():
    uploaded_files = st.session_state.get("txt_uploader")
    txt_dir = st.session_state.get("txt_dir")
    if uploaded_files and txt_dir: handle_upload(uploaded_files, txt_dir)

# --- Streamlit App UI ---
st.set_page_config(layout="wide", page_title="Files-to-Prompt GUI")
with st.expander("README / Instructions", expanded=False): st.markdown(readme_content, unsafe_allow_html=False)
st.title("📄 Files-to-Prompt Context Generator")
st.caption(f"Interface for `{FILES_TO_PROMPT_COMMAND}` & `{LLAMA_PARSE_COMMAND}`.")
did_llama=check_command(LLAMA_PARSE_COMMAND); did_f2p=check_command(FILES_TO_PROMPT_COMMAND); did_auth=False
if did_llama: did_auth = check_llama_parse_auth()
st.info(f"Checks: `{LLAMA_PARSE_COMMAND}`:{'✅' if did_llama else '❌'}, `{FILES_TO_PROMPT_COMMAND}`:{'✅' if did_f2p else '❌'}, Auth:{'✅' if did_auth else ('❔' if not did_llama else '❌')}", icon="ℹ️")

# --- Sidebar ---
with st.sidebar:
    st.header("⚙️ Configuration"); st.subheader("Input Folders")
    # Initialize session state with defaults if keys don't exist
    if 'pdf_dir' not in st.session_state: st.session_state.pdf_dir=os.path.abspath(DEFAULT_PDF_INPUT_DIR)
    if 'txt_dir' not in st.session_state: st.session_state.txt_dir=os.path.abspath(DEFAULT_TXT_INPUT_DIR)
    if 'out_file' not in st.session_state: st.session_state.out_file="context_prompt_output.txt"
    if 'out_loc' not in st.session_state: st.session_state.out_loc=os.path.abspath(".")
    # Widgets read/write session state via 'key' and 'value'
    st.text_input("PDF Input Folder", value=st.session_state.pdf_dir, key="pdf_dir", help="Folder for PDFs.")
    st.text_input("TXT Input Folder", value=st.session_state.txt_dir, key="txt_dir", help="Folder for TXT/MD files.")
    st.subheader("Output Settings")
    parsed_pdf_dir=os.path.join(st.session_state.txt_dir, DEFAULT_PARSED_PDF_OUTPUT_SUBDIR)
    st.info(f"Parsed PDFs ->\n`{parsed_pdf_dir}`\n(Cleared before parsing)")
    st.text_input("Output Filename", value=st.session_state.out_file, key="out_file", help="Output filename.")
    st.text_input("Output Location", value=st.session_state.out_loc, key="out_loc", help="Output directory.")
    final_out_path=os.path.abspath(os.path.join(st.session_state.out_loc, st.session_state.out_file))
    st.info(f"Final context file:\n`{final_out_path}`")

    # --- Add Directory Status / Creation Check ---
    st.markdown("---"); st.subheader("Directory Status")
    dirs_to_ensure = {
        "PDF Input": st.session_state.pdf_dir,
        "TXT Input": st.session_state.txt_dir,
        "Output Location": st.session_state.out_loc,
    }
    all_dirs_ok = True
    for name, dir_path_str in dirs_to_ensure.items():
        dir_path = Path(dir_path_str)
        status_icon = "❔" # Default: Unknown / Not Checked Yet
        try:
            exists_before = dir_path.is_dir()
            dir_path.mkdir(parents=True, exist_ok=True) # Create if needed
            exists_after = dir_path.is_dir() # Check again
            if exists_after and not exists_before: status_icon = "✅ (Created)"
            elif exists_after: status_icon = "✅ (Exists)"
            else: status_icon = "❌ (Failed Create?)"; all_dirs_ok = False # Should not happen if mkdir didn't raise error
        except OSError as e:
            status_icon = f"❌ (OS Error: {e})"
            all_dirs_ok = False
        except Exception as e:
             status_icon = f"❌ (Error: {e})"
             all_dirs_ok = False
        finally:
            # Display status in sidebar
            st.markdown(f"{status_icon} {name}: `{dir_path_str}`")

# --- Main App Area ---
if not all_dirs_ok:
    st.error("One or more essential directories could not be created or accessed. Check permissions/paths in sidebar. App functions may fail.")
    # Optionally st.stop() here if directories are absolutely critical for any display

# --- Tabs ---
tab1, tab2, tab3 = st.tabs(["🚀 Process Files", "📤 PDF Upload", "📝 Plaintext Upload"])

# --- Tab 1: Process Files ---
with tab1:
    # ... (Logic remains the same as the previous version) ...
    st.header("🚀 Process Files")
    pdf_d=st.session_state.pdf_dir; txt_d=st.session_state.txt_dir
    parsed_d=os.path.join(txt_d, DEFAULT_PARSED_PDF_OUTPUT_SUBDIR)
    out_f=os.path.abspath(os.path.join(st.session_state.out_loc, st.session_state.out_file))
    opt=st.radio("Include:", ("TXT only", "PDF only", "Both"), index=2, key="proc_opt", help="Sources.")
    st.write("---")
    if st.button("Generate Context File", key="generate_main", type="primary"):
        ctx_content=None; parse_ok=True; pdf_successes=0; step_ok=True; target_dir=None
        # Step 1: PDF Parsing
        if opt in ["PDF only", "Both"]:
            st.subheader("Step 1: Parsing PDFs")
            parse_ok, pdf_successes, _ = parse_pdfs(pdf_d, parsed_d)
            if not parse_ok and opt == "PDF only": st.error("PDF parsing failed..."); st.stop()
            elif pdf_successes == 0 and opt == "PDF only": st.warning("No PDFs parsed for 'PDF only'."); step_ok = False
        # Step 2: Determine Target Dir & Pre-actions
        if step_ok:
            st.subheader("Step 2: Preparing Combination")
            if opt == "Both":
                if Path(txt_d).is_dir(): target_dir=txt_d; st.write(f"Targeting TXT dir (recursive): `{target_dir}`")
                else: st.error(f"TXT dir invalid ('{txt_d}') for 'Both'."); step_ok=False
            elif opt == "PDF only":
                if pdf_successes > 0 and Path(parsed_d).is_dir(): target_dir=parsed_d; st.write(f"Targeting Parsed PDF dir: `{target_dir}`")
                else: st.warning("No parsed PDFs found for 'PDF only'."); step_ok=False
            elif opt == "TXT only":
                if Path(txt_d).is_dir():
                    st.write("Clearing parsed PDF dir for 'TXT only' mode...")
                    if clear_directory(parsed_d): target_dir=txt_d; st.write(f"Targeting TXT dir (recursive): `{target_dir}`")
                    else: st.error("Failed to clear parsed PDF dir."); step_ok=False
                else: st.error(f"TXT dir invalid ('{txt_d}') for 'TXT only'."); step_ok=False
            # Step 3: Run Combination
            if step_ok and target_dir:
                st.subheader("Step 3: Combining Files")
                combine_status, combined_data = combine_files_via_cli([str(target_dir)], str(out_f))
                if combine_status: ctx_content = combined_data
                else: st.error("Combination failed.")
            elif step_ok: st.warning("No target directory for combination.")
        # Step 4: Display Output
        st.subheader("Step 4: Output Preview")
        if ctx_content: st.success(f"Generated: `{out_f}`."); st.code(ctx_content, language="markdown", line_numbers=True)
        else: st.warning("Context generation incomplete/failed.")

# --- Tab 2: PDF Upload ---
with tab2:
    # ... (Logic remains the same - uses on_change) ...
    st.header("📤 Manage PDF Files"); pdf_dir = st.session_state.pdf_dir
    st.write(f"**Target:** `{pdf_dir}`"); st.markdown("---")
    # Directory existence assured by check after sidebar
    st.subheader("Upload PDFs")
    st.file_uploader("Select PDF files:", type="pdf", accept_multiple_files=True, key="pdf_uploader", on_change=process_pdf_upload)
    st.markdown("---"); st.subheader("Existing PDFs")
    if st.button("🔄 Refresh", key="refresh_pdfs"): pass
    pdf_files = list_files(pdf_dir, "*.pdf")
    if not pdf_files: st.info(f"No PDFs found in `{pdf_dir}`.")
    else:
        st.write(f"{len(pdf_files)} PDF(s):")
        for i, f_obj in enumerate(pdf_files):
            c1, c2 = st.columns([5, 1])
            with c1: st.markdown(f"📄 `{f_obj.name}`", unsafe_allow_html=False)
            with c2:
                if st.button("🗑️", key=f"del_pdf_{i}_{f_obj.name}", help=f"Delete {f_obj.name}"):
                    delete_file(str(f_obj))
            st.divider()

# --- Tab 3: Plaintext Upload ---
with tab3:
    # ... (Logic remains the same - uses on_change) ...
    st.header("📝 Manage Plaintext Files"); txt_dir = st.session_state.txt_dir
    parsed_sub = DEFAULT_PARSED_PDF_OUTPUT_SUBDIR
    st.write(f"**Target:** `{txt_dir}`"); st.caption(f"Note: Subfolder (`{parsed_sub}`) managed automatically.")
    st.markdown("---")
    # Directory existence assured by check after sidebar
    st.subheader("Upload Text/Code/MD Files")
    types = ["txt", "md", "markdown", "json", "xml", "yaml", "yml", "py", "js", "html", "css", "csv", "tsv", "rst"]
    st.file_uploader(f"Select files ({', '.join(types)}):", type=types, accept_multiple_files=True, key="txt_uploader", on_change=process_txt_upload)
    st.markdown("---"); st.subheader("Existing Files (excluding parsed subfolder)")
    if st.button("🔄 Refresh", key="refresh_txts"): pass
    all_f = list_files(txt_dir, "*.*"); parsed_p = Path(txt_dir) / parsed_sub
    txt_disp = [];
    for f in all_f:
        try: f.relative_to(parsed_p)
        except ValueError: txt_disp.append(f)
        except Exception: pass
    if not txt_disp: st.info(f"No user-added files found directly in `{txt_dir}`.")
    else:
        st.write(f"{len(txt_disp)} file(s):")
        for i, f_obj in enumerate(txt_disp):
            c1, c2 = st.columns([5, 1])
            with c1: st.markdown(f"📄 `{f_obj.name}`", unsafe_allow_html=False)
            with c2:
                if st.button("🗑️", key=f"del_txt_{i}_{f_obj.name}", help=f"Delete {f_obj.name}"):
                    delete_file(str(f_obj))
            st.divider()

# --- Footer ---
st.markdown("---")
st.caption(f"Using: `{LLAMA_PARSE_COMMAND}` & `{FILES_TO_PROMPT_COMMAND}`.")