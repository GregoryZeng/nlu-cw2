#!/usr/bin/env bash

rm modified_merge.txt

counter=0
reference=1
baseline=1
lexical=1

while IFS= read -r line; do
    if [[ "$counter" -eq 0 ]] ;then
        counter=1
        echo "$line" >> modified_merge.txt
    elif [[ "$counter" -eq 1 ]]; then
        counter=2
        reference=${line}
        echo "$line" >> modified_merge.txt
    elif [[ "$counter" -eq 2 ]]; then
        counter=3
        baseline=${line}
        echo "$line" >> modified_merge.txt
    elif [[ "$counter" -eq 3 ]]; then
        counter=4
        lexical=${line}
        echo "$line" >> modified_merge.txt
    elif [[ "$counter" -eq 4 ]]; then
        counter=0
        echo ${reference}
        echo ${baseline}
        echo ${lexical}
        echo "\n"
        echo ${reference} > ref.tmp
        echo ${baseline} > baseline.tmp
        echo ${lexical} > lexical.tmp
#        perl multi-bleu.perl -lc <(printf "%s" "$reference") < <(printf "%s" "$baseline") >> modified_merge.txt
#        perl multi-bleu.perl -lc <(printf "%s" "$reference") < <(printf "%s" "$lexical")  >> modified_merge.txt
        perl multi-bleu.perl -lc ref.tmp < baseline.tmp >> modified_merge.txt
        perl multi-bleu.perl -lc ref.tmp < lexical.tmp  >> modified_merge.txt
        printf "\n" >> modified_merge.txt
    fi
#    echo 1
done < merge.txt