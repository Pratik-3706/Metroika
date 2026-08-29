import os
import sys

def main():
    print("====================================================")
    print("      Pre-downloading AI Models for PaddleOCR       ")
    print("====================================================")
    
    try:
        from paddleocr import PaddleOCR
    except ImportError:
        print("[!] PaddleOCR is not installed. Please run setup first.")
        sys.exit(1)
        
    print("[*] Initializing OCR models (this will download them if they don't exist)...")
    # Initialize with the exact flags used in ocr.py to ensure the exact models are cached
    ocr = PaddleOCR(
        use_angle_cls=True,
        use_doc_orientation_classify=True,
        lang="en",
        show_log=True
    )
    print("\n[+] Models downloaded and cached successfully!")

if __name__ == "__main__":
    main()
