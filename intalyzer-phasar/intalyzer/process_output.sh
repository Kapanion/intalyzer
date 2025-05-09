awk '
BEGIN {
	total = 0
	idx = 0
}
/\.ll:$/ {
	current_file = $0
	sub(/:$/, "", current_file)
	filenames[++idx] = current_file
	in_race = 0
	next
}
/^Race Consitions:/ { in_race = 1; next }
in_race && $0 ~ /\S/ {
	counts[current_file]++
	total++
	next
}
in_race && $0 ~ /^$/ {
	in_race = 0
}
END {
	print "Race Conditions per file:" > "final_output.txt"
	for (i = 1; i <= idx; i++) {
		file = filenames[i]
		printf "%s: %d\n", file, counts[file] >> "final_output.txt"
	}
	printf "\nTotal Race Conditions: %d\n", total >> "final_output.txt"
}
' combined_output.txt
