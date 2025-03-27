# -*- coding: utf-8 -*-
import streamlit as st
import os
import subprocess
import shutil
import shlex
from pathlib import Path
import logging
from typing import Tuple, Optional
# Import Google AI SDK
import google.generativeai as genai

# --- Configuration ---
DEFAULT_PDF_INPUT_DIR = "pdfs_to_parse"
DEFAULT_TXT_INPUT_DIR = "txt_files"
DEFAULT_PARSED_PDF_OUTPUT_SUBDIR = "parsed_pdfs_streamlit"
LLAMA_PARSE_COMMAND = "llama-parse"
FILES_TO_PROMPT_COMMAND = "files-to-prompt"
LLAMA_PARSE_CONFIG_FILE = os.path.expanduser("~/.llama-parse/config.json")
README_FILE = "README.md"

# --- Gemini Configuration ---
MODEL_NAME = "gemini-2.5-pro-exp-03-25" # Using requested model (verified as existing on 2025-03-27)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Load API Key from Environment Variable ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY: logger.warning("Env var 'GEMINI_API_KEY' not found/empty.")
else: logger.info("Loaded GEMINI_API_KEY from environment.")

# --- Default Meta Prompt ---
DEFAULT_META_PROMPT_TEMPLATE = """Analyze the following text extracted from a larger context document (formatted with XML tags like <document path="...">). Identify the primary subject matter, domain, or key technologies discussed.

Based on this analysis, generate a longform, detailed system prompt suitable for another thinking AI assistant. This system prompt should:
1. Instruct the assistant to adopt the persona of a knowledgeable expert in the identified domain/subject (e.g., "You are an expert Python developer specializing in data analysis libraries...").
2. Emphasize using the *full context* (which will be provided to the assistant separately) to answer questions accurately, comprehensively, and preferentially on the provided documents.
3. Guide the assistant to cite the source document path when possible or relevant.
4. Guide the assistant to use its search tool to extend or verify information when needed.
4. Avoid mentioning the snippet analysis process in the final output.

Output *only* the generated system prompt text, with no extra explanations, preamble, or formatting like markdown quotes.

Context:
-------
{context_snippet}
-------
Generated System Prompt:"""

# --- Helper Functions ---
def display_error(message): st.toast(f"❌ Error: {message}", icon="❌")
def display_success(message): st.toast(f"✅ Success: {message}", icon="✅")
def display_warning(message): st.toast(f"⚠️ Warning: {message}", icon="⚠️")
def display_info(message): st.toast(f"ℹ️ Info: {message}", icon="ℹ️")
def check_command(cmd): return shutil.which(cmd) is not None or st.warning(f"'{cmd}' not found.", icon="⚠️") is None
def check_llama_parse_auth():
    if not os.path.exists(LLAMA_PARSE_CONFIG_FILE): st.error(f"**Auth Missing:** Config (`{LLAMA_PARSE_CONFIG_FILE}`) missing...", icon="🔑"); return False
    return True
def list_files(directory, pattern="*.*"):
    if not directory: return []
    dp=Path(directory);
    if not dp.is_dir(): return []
    try: return sorted([f for f in dp.glob(pattern) if f.is_file()])
    except Exception as e: display_error(f"List files error '{directory}': {e}"); return []
def handle_upload(up_files, target_dir):
    if not up_files or not target_dir: return 0
    saved=0; skipped=0; tp=Path(target_dir)
    try:
        tp.mkdir(parents=True, exist_ok=True)
        for f in up_files:
            dest=tp/f.name;
            if dest.exists(): display_warning(f"Overwriting: '{f.name}'")
            try: dest.write_bytes(f.getbuffer()); saved+=1
            except Exception as e: display_error(f"Save failed '{f.name}': {e}"); skipped+=1
        if saved > 0: display_success(f"Processed {saved} uploaded file(s).")
        if skipped > 0: display_error(f"Failed {skipped} upload(s).")
    except Exception as e: display_error(f"Upload error: {e}")
    return saved
def delete_file(fp_str):
    try:
        if not fp_str: display_warning("Empty path for deletion."); return
        fp=Path(fp_str);
        if fp.is_file(): fn=fp.name; fp.unlink(); display_success(f"Deleted '{fn}'. Refreshing..."); st.rerun()
        else: display_warning(f"Not found: '{fp_str}'")
    except Exception as e: display_error(f"Delete error '{fp_str}': {e}")
def clear_directory(dir_str):
    dp=Path(dir_str); cleared=False
    if dp.exists():
        try: shutil.rmtree(dp); dp.mkdir(parents=True, exist_ok=True); display_info(f"Cleared: '{dir_str}'"); cleared=True
        except OSError as e: display_error(f"Failed clear dir '{dir_str}': {e}"); cleared=False
    else:
        try: dp.mkdir(parents=True, exist_ok=True); cleared=True
        except OSError as e: display_error(f"Failed create dir '{dir_str}': {e}"); cleared=False
    return cleared

# --- Gemini Interface Function ---
def generate_expert_system_prompt(full_context: str, meta_prompt_template: str) -> Tuple[Optional[str], Optional[str]]:
    if not GEMINI_API_KEY: return None, "Config Error: Env var 'GEMINI_API_KEY' not set."
    if not full_context or not full_context.strip(): return None, "Input Error: Context empty."
    if not meta_prompt_template or '{context_snippet}' not in meta_prompt_template: return None, "Input Error: Meta-prompt invalid."
    try: genai.configure(api_key=GEMINI_API_KEY)
    except Exception as e: logger.error(f"Config SDK error: {e}"); return None, f"API Config Error: {e}"
    ctx_snippet = full_context.strip(); logger.info(f"Sending context len {len(ctx_snippet)} to Gemini.")
    try: final_meta_prompt = meta_prompt_template.format(context_snippet=ctx_snippet)
    except Exception as e: logger.error(f"Format meta-prompt error: {e}"); return None, f"Meta-Prompt Format Error: {e}"
    try:
        logger.info(f"Generating prompt using model: {MODEL_NAME}...")
        model = genai.GenerativeModel(MODEL_NAME)
        resp = model.generate_content(final_meta_prompt, generation_config=genai.types.GenerationConfig(temperature=0.5), safety_settings={'HATE': 'BLOCK_ONLY_HIGH'})
        if hasattr(resp, 'text'):
            gen_prompt = resp.text.strip()
            if not gen_prompt:
                 if resp.prompt_feedback.block_reason: reason = resp.prompt_feedback.block_reason.name; logger.warning(f"Blocked: {reason}"); return None, f"Blocked ({reason})."
                 else: logger.warning("Gen response empty."); return None, "Error: Empty response from AI."
            logger.info("Generated suggestion."); return gen_prompt, None
        elif resp.prompt_feedback.block_reason: reason = resp.prompt_feedback.block_reason.name; logger.warning(f"Blocked (no text): {reason}"); return None, f"Blocked ({reason})."
        else: logger.error(f"Unexpected response: {resp}"); return None, "Error: Unexpected response structure."
    except Exception as e:
        logger.error(f"API call error ('{MODEL_NAME}'): {e}", exc_info=True)
        err=str(e).lower();
        if "api key not valid" in err: return None, "API Error: Invalid Key (check env var)."
        elif "quota" in err: return None, "API Error: Quota exceeded."
        elif "model" in err and ("not found" in err or "permission" in err): return None, f"API Error: Model '{MODEL_NAME}' not found/denied."
        else: return None, f"API Error: {e}"

# --- Core Processing Functions ---
def parse_pdfs(pdf_in_dir, parsed_out_dir):
    """Parses PDFs. Clears output dir first."""
    # ... (remains same) ...
    st.write(f"Parsing PDFs from: `{pdf_in_dir}` -> `{parsed_out_dir}`")
    if not check_command(LLAMA_PARSE_COMMAND): return False, 0, 0
    if not check_llama_parse_auth(): return False, 0, 0
    pdf_in=Path(pdf_in_dir); parsed_out=Path(parsed_out_dir)
    if not pdf_in.is_dir(): display_error(f"PDF Input Dir not found: '{pdf_in_dir}'"); return False, 0, 0
    st.write(f"Preparing: `{parsed_out_dir}`...")
    try:
        if parsed_out.exists(): shutil.rmtree(parsed_out)
        parsed_out.mkdir(parents=True, exist_ok=True)
    except OSError as e: display_error(f"Output dir error '{parsed_out_dir}': {e}"); return False, 0, 0
    pdfs = list_files(pdf_in_dir, "*.pdf")
    if not pdfs: st.warning(f"No PDFs found in '{pdf_in_dir}'.", icon="ℹ️"); return True, 0, 0
    st.write(f"Found {len(pdfs)} PDF(s)."); prog = st.progress(0); ok=0; fail=0; env = os.environ.copy()
    for i, pdf in enumerate(pdfs):
        pdf_s=str(pdf); base=pdf.stem; out_n=f"{base}.md"; out_f=parsed_out/out_n; out_f_s=str(out_f)
        st.write(f"Processing '{pdf.name}'...")
        try:
            cmd=[LLAMA_PARSE_COMMAND, "parse", pdf_s, "-o", out_f_s, "--format", "markdown"]
            res=subprocess.run(cmd, capture_output=True, text=True, check=False, env=env, timeout=300)
            if res.returncode==0 and out_f.exists(): ok+=1; st.write(f"-> Parsed to '{out_n}'")
            elif res.returncode==0: st.write("-> WARN: Output missing."); fail+=1
            else:
                fail+=1; st.write(f"-> ERROR: LlamaParse fail ({res.returncode}) for '{pdf.name}'.")
                with st.expander("Show Output/Error"):
                    if res.stdout: st.text_area("Out", res.stdout.strip(), height=100, key=f"out_{pdf.name}")
                    if res.stderr: st.text_area("Err", res.stderr.strip(), height=100, key=f"err_{pdf.name}")
        except Exception as e: st.write(f"-> ERROR: {e}"); fail+=1
        finally: prog.progress((i + 1) / len(pdfs))
    st.write(f"--- Parsing Summary --- OK: {ok}, Fail: {fail}")
    if fail > 0: display_error(f"{fail} PDF(s) failed."); return False, ok, fail
    elif ok > 0: display_success("PDF parsing complete."); return True, ok, fail
    else:
        if len(pdfs) > 0: display_info("No PDFs parsed.")
        return True, ok, fail

def combine_files_via_cli(dirs_scan, out_fp_s):
    """Combines files using files-to-prompt (recursive)."""
    # ... (remains same) ...
    st.write(f"Combining via '{FILES_TO_PROMPT_COMMAND}' CLI...")
    if not check_command(FILES_TO_PROMPT_COMMAND): return False, None
    if not dirs_scan: display_error("No input dirs."); return False, None
    valid=[str(d.resolve()) for ds in dirs_scan if (d:=Path(ds)).is_dir() or st.warning(f"Skip invalid dir: '{ds}'")]
    if not valid: display_error("No valid dirs."); return False, None
    out_fp=Path(out_fp_s).resolve(); out_dir=out_fp.parent
    try: out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e: display_error(f"Output dir error '{out_dir}': {e}"); return False, None
    quoted_out=shlex.quote(str(out_fp))
    cmd=[FILES_TO_PROMPT_COMMAND] + [shlex.quote(d) for d in valid] + ["--cxml", "-o", quoted_out]
    st.info(f"Combining: `{', '.join(valid)}` (Recursive)"); st.write(f"Exec: `{' '.join(cmd)}`")
    try:
        res=subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=300)
        if res.returncode==0 and out_fp.exists():
            display_success(f"Combined: '{out_fp}'")
            try: return True, out_fp.read_text(encoding="utf-8")
            except IOError as e: display_error(f"Read fail '{out_fp}': {e}"); return False, None
        elif res.returncode==0: display_error(f"Cmd ok, output missing: '{out_fp}'."); return False, None
        else:
            display_error(f"'{FILES_TO_PROMPT_COMMAND}' fail ({res.returncode}).")
            if res.stderr: st.text_area(f"{FILES_TO_PROMPT_COMMAND} Error", res.stderr.strip(), height=100, key="f2p_err")
            return False, None
    except Exception as e: display_error(f"Run error '{FILES_TO_PROMPT_COMMAND}': {e}"); return False, None

# --- Load README ---
def load_readme():
    # ... (remains same) ...
    content = f"Error loading {README_FILE}"; script_d = Path(__file__).parent; p = script_d / README_FILE
    if not p.exists(): p = Path.cwd() / README_FILE
    try:
        if p.exists(): content = p.read_text(encoding="utf-8")
        else: content = f"Error: {README_FILE} not found in {script_d} or {Path.cwd()}."
    except Exception as e: content = f"Error reading {README_FILE}: {e}"
    return content
readme_content = load_readme()

# --- Upload/Reset Callbacks ---
def process_pdf_upload():
    uploaded = st.session_state.get("pdf_uploader"); pdf_dir = st.session_state.get("pdf_dir")
    if uploaded and pdf_dir: handle_upload(uploaded, pdf_dir)
    # REMOVED state assignment - Cannot assign to file_uploader state
def process_txt_upload():
    uploaded = st.session_state.get("txt_uploader"); txt_dir = st.session_state.get("txt_dir")
    if uploaded and txt_dir: handle_upload(uploaded, txt_dir)
    # REMOVED state assignment

def reset_meta_prompt_callback():
    """Sets the meta_prompt_template state back to its default."""
    st.session_state.meta_prompt_template = DEFAULT_META_PROMPT_TEMPLATE
    st.toast("Meta-prompt template reset to default.", icon="🔄")

# --- Streamlit App UI ---
st.set_page_config(layout="wide", page_title="Files-to-Prompt GUI")
with st.expander("README / Instructions", expanded=False): st.markdown(readme_content, unsafe_allow_html=False)
st.title("📄 Files-to-Prompt Context Generator")
st.caption(f"Interface for `{FILES_TO_PROMPT_COMMAND}` & `{LLAMA_PARSE_COMMAND}`.")
did_llama=check_command(LLAMA_PARSE_COMMAND); did_f2p=check_command(FILES_TO_PROMPT_COMMAND); did_auth=False
if did_llama: did_auth = check_llama_parse_auth()
st.info(f"Checks: `{LLAMA_PARSE_COMMAND}`:{'✅' if did_llama else '❌'}, `{FILES_TO_PROMPT_COMMAND}`:{'✅' if did_f2p else '❌'}, Auth:{'✅' if did_auth else ('❔' if not did_llama else '❌')}", icon="ℹ️")

# --- Initialize Session State (Globally) ---
if 'pdf_dir' not in st.session_state: st.session_state.pdf_dir=os.path.abspath(DEFAULT_PDF_INPUT_DIR)
if 'txt_dir' not in st.session_state: st.session_state.txt_dir=os.path.abspath(DEFAULT_TXT_INPUT_DIR)
if 'out_file' not in st.session_state: st.session_state.out_file="context_prompt_output.txt"
if 'out_loc' not in st.session_state: st.session_state.out_loc=os.path.abspath(".")
if 'ctx_content' not in st.session_state: st.session_state.ctx_content = None
if 'suggested_system_prompt' not in st.session_state: st.session_state.suggested_system_prompt = ""
if 'suggestion_error' not in st.session_state: st.session_state.suggestion_error = None
if 'meta_prompt_template' not in st.session_state: st.session_state.meta_prompt_template = DEFAULT_META_PROMPT_TEMPLATE

# --- Sidebar ---
with st.sidebar:
    # ... (Sidebar remains same) ...
    st.header("⚙️ Configuration"); st.subheader("Input Folders")
    st.text_input("PDF Input Folder", value=st.session_state.pdf_dir, key="pdf_dir", help="Folder for PDFs.")
    st.text_input("TXT Input Folder", value=st.session_state.txt_dir, key="txt_dir", help="Folder for TXT/MD files.")
    st.subheader("Output Settings")
    parsed_pdf_dir=os.path.join(st.session_state.txt_dir, DEFAULT_PARSED_PDF_OUTPUT_SUBDIR)
    st.info(f"Parsed PDFs ->\n`{parsed_pdf_dir}`\n(Cleared before parsing)")
    st.text_input("Output Filename", value=st.session_state.out_file, key="out_file", help="Output filename.")
    st.text_input("Output Location", value=st.session_state.out_loc, key="out_loc", help="Output directory.")
    final_out_path=os.path.abspath(os.path.join(st.session_state.out_loc, st.session_state.out_file))
    st.info(f"Final context file:\n`{final_out_path}`")
    st.markdown("---"); st.subheader("Directory Status")
    dirs_to_ensure = {"PDF Input": st.session_state.pdf_dir, "TXT Input": st.session_state.txt_dir, "Output Location": st.session_state.out_loc,}
    all_dirs_ok = True
    for name, dir_path_str in dirs_to_ensure.items():
        dir_path = Path(dir_path_str); status_icon = "❔"
        try:
            exists = dir_path.is_dir(); dir_path.mkdir(parents=True, exist_ok=True); created = not exists and dir_path.is_dir()
            if created: status_icon = "✅ (Created)"
            elif exists: status_icon = "✅ (Exists)"
            else: status_icon = "❌"; all_dirs_ok = False
        except OSError as e: status_icon = f"❌ (OS Error)"; all_dirs_ok = False; st.error(f"OS Error: {name}: {e}")
        except Exception as e: status_icon = f"❌ (Error)"; all_dirs_ok = False; st.error(f"Error: {name}: {e}")
        st.markdown(f"{status_icon} {name}: `{dir_path_str}`")

# --- Main App Area ---
if not all_dirs_ok: st.error("Essential directories non-functional. Check sidebar/permissions.")

# --- Tabs ---
tab1, tab2, tab3 = st.tabs(["🚀 Process Files", "📤 PDF Upload", "📝 Plaintext Upload"])

# --- Tab 1: Process Files ---
with tab1:
    st.header("🚀 Process Files")
    pdf_d=st.session_state.pdf_dir; txt_d=st.session_state.txt_dir
    parsed_d=os.path.join(txt_d, DEFAULT_PARSED_PDF_OUTPUT_SUBDIR)
    out_f=os.path.abspath(os.path.join(st.session_state.out_loc, st.session_state.out_file))
    opt=st.radio("Include:", ("TXT only", "PDF only", "Both"), index=2, key="proc_opt", help="Sources.")
    st.write("---")

    if st.button("Generate Context File", key="generate_main", type="primary"):
        # ... (Processing logic remains same) ...
        st.session_state.ctx_content = None; st.session_state.suggested_system_prompt = ""; st.session_state.suggestion_error = None
        parse_ok=True; pdf_successes=0; step_ok=True; target_dir=None
        if opt in ["PDF only", "Both"]:
            st.subheader("Step 1: Parsing PDFs")
            parse_ok, pdf_successes, _ = parse_pdfs(pdf_d, parsed_d)
            if not parse_ok and opt == "PDF only": st.error("PDF parsing failed..."); st.stop()
            elif pdf_successes == 0 and opt == "PDF only": st.warning("No PDFs parsed for 'PDF only'."); step_ok = False
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
            if step_ok and target_dir:
                st.subheader("Step 3: Combining Files")
                combine_status, combined_data = combine_files_via_cli([str(target_dir)], str(out_f))
                if combine_status: st.session_state.ctx_content = combined_data
                else: st.error("Combination failed.")
            elif step_ok: st.warning("No target directory for combination.")

    # --- Display Output Preview and Gemini Suggestion ---
    st.subheader("Step 4: Output Preview")
    if st.session_state.ctx_content:
        st.success(f"Context generated: `{out_f}`.")
        st.code(st.session_state.ctx_content, language="markdown", line_numbers=True)

        # --- Gemini Suggestion Section ---
        st.divider()
        st.subheader("🤖 Suggest Expert System Prompt (via Gemini)")
        st.caption(f"Uses the **full context** above and the `{MODEL_NAME}` model.")

        with st.expander("⚙️ Edit Meta-Prompt Template for Gemini"):
            st.text_area(
                "Template:",
                value=st.session_state.meta_prompt_template, # Reads from state
                key="meta_prompt_template",                 # Writes to state on edit
                height=300,
                help="Edit Gemini instructions. Use {context_snippet} placeholder."
            )
            # Reset button uses callback
            st.button(
                "Reset to Default Template",
                key="reset_meta_prompt",
                on_click=reset_meta_prompt_callback # Assign callback
            )

        if st.button("✨ Suggest System Prompt", key="suggest_prompt_btn"):
            st.session_state.suggested_system_prompt = ""; st.session_state.suggestion_error = None
            with st.spinner("Generating prompt suggestion... (using full context)"):
                try:
                    # Call function defined in this file
                    gen_prompt, err_msg = generate_expert_system_prompt(
                        st.session_state.ctx_content,
                        st.session_state.meta_prompt_template # Pass current (potentially edited) template
                    )
                    if err_msg: st.session_state.suggestion_error = err_msg
                    elif gen_prompt: st.session_state.suggested_system_prompt = gen_prompt
                    else: st.session_state.suggestion_error = "No prompt or error returned."
                except Exception as e: st.session_state.suggestion_error = f"Unexpected error: {e}"; st.exception(e)

        if st.session_state.suggestion_error: st.error(st.session_state.suggestion_error)
        st.markdown("**Suggested System Prompt:**")
        # Display using st.code for copy functionality
        st.code(st.session_state.suggested_system_prompt, language=None, line_numbers=False)
        # --- End of Gemini Suggestion Section ---

    else:
         if 'generate_main' in st.session_state and st.session_state.generate_main:
              st.warning("Context generation failed or not yet run.")

# --- Tab 2: PDF Upload ---
with tab2:
    # ... (remains same) ...
    st.header("📤 Manage PDF Files"); pdf_dir = st.session_state.pdf_dir
    st.write(f"**Target:** `{pdf_dir}`"); st.markdown("---")
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
                if st.button("🗑️", key=f"del_pdf_{i}_{f_obj.name}", help=f"Delete {f_obj.name}"): delete_file(str(f_obj))
            st.divider()


# --- Tab 3: Plaintext Upload ---
with tab3:
    # ... (remains same) ...
    st.header("📝 Manage Plaintext Files"); txt_dir = st.session_state.txt_dir
    parsed_sub = DEFAULT_PARSED_PDF_OUTPUT_SUBDIR
    st.write(f"**Target:** `{txt_dir}`"); st.caption(f"Note: Subfolder (`{parsed_sub}`) managed automatically.")
    st.markdown("---")
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
                if st.button("🗑️", key=f"del_txt_{i}_{f_obj.name}", help=f"Delete {f_obj.name}"): delete_file(str(f_obj))
            st.divider()


# --- Footer ---
st.markdown("---")
st.caption(f"Using: `{LLAMA_PARSE_COMMAND}` & `{FILES_TO_PROMPT_COMMAND}`.")