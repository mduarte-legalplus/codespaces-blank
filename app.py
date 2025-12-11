import streamlit as st
from pypdf import PdfReader, PdfWriter
import io

st.set_page_config(page_title="Simple PDF Merger", page_icon="🔗", layout="centered")

st.title("🔗 Simple PDF Merger")
st.write("Upload your signature pages, and this tool will combine them into one document.")

# 1. Upload Multiple Files
uploaded_files = st.file_uploader(
    "Drop your signature pages here:", 
    type="pdf", 
    accept_multiple_files=True
)

# 2. The Merge Logic
if uploaded_files:
    if st.button("Merge Documents Now", type="primary"):
        writer = PdfWriter()
        
        # Create a progress bar
        progress_bar = st.progress(0)
        
        try:
            # Loop through each uploaded file
            for i, file in enumerate(uploaded_files):
                reader = PdfReader(file)
                # Add every page from this file to the new one
                for page in reader.pages:
                    writer.add_page(page)
                
                # Update progress
                progress_bar.progress((i + 1) / len(uploaded_files))
                st.success(f"✅ Added: {file.name}")

            # 3. Download
            output_pdf = io.BytesIO()
            writer.write(output_pdf)
            
            st.divider()
            st.download_button(
                label="⬇️ Download Combined PDF",
                data=output_pdf.getvalue(),
                file_name="combined_packet.pdf",
                mime="application/pdf",
                use_container_width=True
            )
            
        except Exception as e:
            st.error(f"Error merging files: {e}")
            st.info("Tip: If the error mentions 'AES', ensure you ran 'pip install cryptography' in the terminal.")