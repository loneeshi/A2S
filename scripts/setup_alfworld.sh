#!/bin/bash
# Setup script for ALFWorld integration
# Run this in conda environment: skilltree_py311

echo "========================================="
echo "  ALFWorld Integration Setup"
echo "========================================="
echo ""

# Check conda environment
if [[ -z "$CONDA_DEFAULT_ENV" ]]; then
    echo "❌ Error: No conda environment activated"
    echo "Please run: conda activate skilltree_py311"
    exit 1
fi

echo "✅ Current conda environment: $CONDA_DEFAULT_ENV"
echo ""

# Install ALFWorld
echo "Step 1: Installing ALFWorld..."
pip install alfworld

echo ""
echo "Step 2: Verifying installation..."
python -c "import alfworld; print(f'✅ ALFWorld installed successfully')"

echo ""
echo "Step 3: Checking ALFWorld data files..."
python -c "
import os
alfworld_data = os.path.expanduser('~/.alfworld')
if os.path.exists(alfworld_data):
    print(f'✅ ALFWorld data directory exists: {alfworld_data}')
else:
    print(f'⚠️  ALFWorld data directory not found: {alfworld_data}')
    print('You may need to download data separately')
"

echo ""
echo "========================================="
echo "  Setup Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "  1. Download ALFWorld data if needed"
echo "  2. Run test: python scripts/test_alfworld_real.py"
echo ""
