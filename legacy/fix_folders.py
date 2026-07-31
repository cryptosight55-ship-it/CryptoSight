import os

# Create all needed folders
folders = ['data', 'models', 'logs', 'data/labeled', 'data/raw']

for folder in folders:
    os.makedirs(folder, exist_ok=True)
    print(f"✅ Created folder: {folder}")

print("✅ All folders are ready!")