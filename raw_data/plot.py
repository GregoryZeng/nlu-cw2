import seaborn as sns
import numpy as np

with open('./train.en') as f:
    en = [s.strip().split(' ') for s in f]
    en_len = np.array(list(map(len, en)))

with open('./train.jp') as f:
    jp = [s.strip().split(' ') for s in f]
    jp_len = np.array(list(map(len, jp)))


ax = sns.scatterplot(x=en_len, y=jp_len,marker='.')
ax.set(xlabel='English word length', ylabel='Japanese word length')
ax.get_figure().savefig('a.pdf')