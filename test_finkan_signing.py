
import os
import sys
import time

# Add the project root to sys.path to ensure modules are importable
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from paradigm.model import ModelEnum, load_model_args, ModelFormatOutput
from model.FINKAN.instance import FINKAN_MODEL_INSTANCE
from signer.certification import CertificateManager

def test_finkan_3000_rows_signing():
    print(f"Project root: {project_root}")
    
    # 1. Load FINKAN model
    print("\n--- 1. Initializing FINKAN model ---")
    try:
        model_args = load_model_args(model=ModelEnum.FINKAN, is_cuda=False)
        model = FINKAN_MODEL_INSTANCE(model_args=model_args)
    except Exception as e:
        print(f"Error initializing FINKAN: {e}")
        return

    # 2. Generate 3000 rows
    print("\n--- 2. Generating 3000 rows of data ---")
    start_time = time.time()
    try:
        # FINKAN generate_output will produce a DataFrame in output.output
        output: ModelFormatOutput = model.generate_output(num_samples=3000)
    except Exception as e:
        print(f"Error during data generation: {e}")
        return
    gen_duration = time.time() - start_time
    print(f"Data generation took {gen_duration:.2f} seconds.")

    df = output.output
    print(f"Generated DataFrame shape: {df.shape}")

    # 3. Convert to bytes (simulating Storager.py logic)
    print("\n--- 3. Serializing to JSON (Storager simulation) ---")
    start_time = time.time()
    # In Storager.py, it converts to JSON and then to bytes.
    json_data = df.to_json()
    data_bytes = json_data.encode('utf-8')
    serialize_duration = time.time() - start_time
    print(f"Serialization tool {serialize_duration:.2f} seconds.")
    print(f"Serialized data size: {len(data_bytes) / (1024*1024):.2f} MB")

    # 4. Sign data
    print("\n--- 4. Signing data with CertificationManager ---")
    print("Note: You should see Go-side logs (Entering C_SignSlot...) in the console below.")
    try:
        cert_manager = CertificateManager()
        start_time = time.time()
        # This will call the rebuilt libgo.so
        signature = cert_manager.sign_data(data_bytes)
        sign_duration = time.time() - start_time
        print(f"Python-side: sign_data returned in {sign_duration:.2f} seconds.")
        print(f"Signature (base64, preview): {signature[:60]}...")
        
        # Verify it can be decoded
        import base64
        decoded_sig = base64.b64decode(signature)
        print(f"Binary signature length: {len(decoded_sig)} bytes")
        
    except Exception as e:
        print(f"Error during signing: {e}")
        return

    if signature:
        print("\nSUCCESS: All steps completed normally with the NEW libgo.so.")
    else:
        print("\nFAILURE: Signature is empty.")

if __name__ == "__main__":
    test_finkan_3000_rows_signing()
