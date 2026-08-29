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
    
    print("[*] Pre-downloading OCR drawing fonts (simfang.ttf)...")
    try:
        import numpy as np
        import tempfile
        
        # Create a tiny 10x10 black image in memory
        dummy_img = np.zeros((10, 10, 3), dtype=np.uint8)
        
        # Run a quick fake scan
        result = ocr.predict(dummy_img)
        
        # Try to save the fake scan to trigger the font download
        with tempfile.TemporaryDirectory() as temp_dir:
            for res in result:
                res.save_to_img(save_path=temp_dir)
        print("[+] Fonts cached successfully!")
    except Exception as e:
        print(f"[-] Note: Font pre-download skipped ({e}). It will download on first use.")

if __name__ == "__main__":
    main()
