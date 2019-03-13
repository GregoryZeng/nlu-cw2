import nltk

with open('./raw_data/test.jp') as f:
    jp = f.readlines()
with open('./raw_data/test.en') as f:
    ref = f.readlines()
with open('./translate_baseline.txt') as f:
    base = f.readlines()
with open('./new_lexical_model_translations.txt') as f:
    lex = f.readlines()


with open('./vbd_filter.txt','w') as f:
    for i in range(len(ref)):
        pos_seq = nltk.pos_tag(ref[i].split(' '))
        vbd_tokens = [t for t in pos_seq if t[1]=='VBD']
        if len(vbd_tokens) == 0:
            continue
        f.write(jp[i])
        f.write(ref[i])
        f.write(base[i])
        f.write(lex[i])
        f.write('\n')
