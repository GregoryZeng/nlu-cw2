import seaborn as sns
import numpy as np
import pandas as pd
from scipy.stats import pearsonr

with open('./train.en') as f:
    en = [s.strip().split(' ') for s in f]
    en_len = np.array(list(map(len, en)))

with open('./train.jp') as f:
    jp = [s.strip().split(' ') for s in f]
    jp_len = np.array(list(map(len, jp)))

len_df = pd.DataFrame({'en_len':en_len, 'jp_len':jp_len})
unique_len_df = len_df.groupby(['en_len','jp_len']).size().reset_index()
unique_len_df.columns.values[2]='size'


# ax = sns.scatterplot(data=unique_len_df,x='en_len',y='jp_len',size='size',marker='o')
# ax.set(xlabel='English word length', ylabel='Japanese word length')
# ax.get_figure().savefig('o.pdf')

ax=sns.lmplot(data=len_df,x='en_len',y='jp_len',x_jitter=.2,y_jitter=.2,markers='.')
ax.set(xlabel='English sentence length', ylabel='Japanese sentence length')
ax.savefig('lm.pdf')

print(f'pearson:{pearsonr(en_len,jp_len)}')
