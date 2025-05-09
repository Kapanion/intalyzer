#!/bin/bash

ll_dir="$1"

> combined_output.txt

for file in "$ll_dir"*.ll; do
	../../build/tools/intalyzer/intalyzer "$file"
	
	echo "$file:" >> combined_output.txt
	cat output.txt >> combined_output.txt
	echo >> combined_output.txt
done
