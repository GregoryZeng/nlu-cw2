with open('./raw_data/test.jp') as f:
    jp = f.readlines()
with open('./raw_data/test.en') as f:
    ref = f.readlines()
with open('./translate_baseline.txt') as f:
    base = f.readlines()
with open('./translate_lexical.txt') as f:
    lex = f.readlines()


with open('./merge.txt','w') as f:
    for i in range(len(ref)):
        f.write(jp[i])
        f.write(ref[i])
        f.write(base[i])
        f.write(lex[i])
        f.write('\n')
