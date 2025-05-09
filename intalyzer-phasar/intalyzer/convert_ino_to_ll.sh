#!/bin/bash
set -e

INO_DIR="$1"           # Input directory with .ino files
OUT_DIR="$2"           # Output directory for .cpp/.ll files
DUMMY_DIR="$3"         # Auto-generated dummy headers directory
INO2CPP="$4"		# Path to your ino2cpp converter

# Create output directories
mkdir -p "$OUT_DIR" "$DUMMY_DIR"
chmod -R +w "$OUT_DIR"

# Convert .ino to .cpp (FLAT structure)
echo "Step 1/3: Converting .ino to .cpp..."
find "$INO_DIR" -name "*.ino" -exec bash -c '
  ino_file="$1"
  base_name=$(basename "$ino_file" .ino | tr " " "_")
  python3 "'"$INO2CPP"'" "$ino_file"
' _ {} \;

# Generate dummy headers
echo "Step 2/3: Generating dummy headers..."
grep -rh '#include' "$OUT_DIR" | awk -F '[<>\"]' '{print $2}' | sort -u | while read header; do
  [[ -z "$header" ]] && continue
  if ! clang++ -E -x c++ - </dev/null 2>&1 | grep -q "$header"; then
    mkdir -p "$DUMMY_DIR/$(dirname "$header")"
  
      class_name=$(basename "${header%.*}")
      echo "class $class_name {};" > "$DUMMY_DIR/$header"
  fi
done

# Compile to LLVM IR
echo "Step 3/3: Compiling to .ll..."
find "$OUT_DIR" -name "*.cpp" -print0 | while IFS= read -r -d '' cpp_file; do
  ll_file="${cpp_file%.*}.ll"
  echo "Processing: $cpp_file → $ll_file"
  
  clang++ -S -emit-llvm --target=avr -mmcu=atmega328p -DF_CPU=16000000L -I../.arduino15/packages/arduino/tools/avr-gcc/7.3.0-atmel3.6.1-arduino7/avr/include -I../.arduino15/packages -I/usr/include -I../.arduino15/packages/arduino/hardware/avr/1.8.6/variants/standard -I../.arduino15/packages/arduino/hardware/avr/1.8.6/cores/arduino -I../dummy_headers "$cpp_file" -o "$ll_file" 2>"${cpp_file%.*}.err" || true

done

echo "IR files generated in: $OUT_DIR"
