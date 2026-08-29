import os
import sys

def main():
    print("====================================================")
    print("      Pre-downloading AI Models for PaddleOCR       ")
    print("====================================================")
    
    try:
        import os
        os.environ["FLAGS_enable_pir_api"] = "0"
        os.environ["FLAGS_use_mkldnn"] = "0"
        from paddleocr import PaddleOCR
    except ImportError:
        print("[!] PaddleOCR is not installed. Please run setup first.")
        sys.exit(1)
        
    print("[*] Initializing OCR models (this will download them if they don't exist)...")
    # Initialize with the exact flags used in ocr.py to ensure the exact models are cached
    ocr = PaddleOCR(
        use_textline_orientation=True,
        use_doc_orientation_classify=True,
        lang="en",
        enable_mkldnn=False
    )
    print("\n[+] Models downloaded and cached successfully!")

if __name__ == "__main__":
    main()
