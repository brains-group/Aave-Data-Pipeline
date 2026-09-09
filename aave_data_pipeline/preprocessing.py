"""Train-fitted R-style preprocessing, with explicit target/identity separation.

The original R test encoding fits dummy columns independently. Here categories
are fitted once; unseen values map to Other. PCA/scaling never fit on test rows.
"""
import numpy as np
import pandas as pd

IDENTITY = ['id','observation_id','outcome_id','split','Index Event','Outcome Event','type','pool','user','timestamp']
TARGETS = ['timeDiff','status']

class Preprocessor:
    def __init__(self, scaling=True, encoding=True, pca_variance=None):
        self.scaling,self.encoding,self.pca_variance=scaling,encoding,pca_variance

    def fit(self, train):
        frame=train.drop(columns=IDENTITY+TARGETS,errors='ignore')
        self.numeric=list(frame.select_dtypes(include=np.number).columns)
        self.categories={}
        for c in frame.columns.difference(self.numeric):
            values=frame[c].astype('string').fillna('Other')
            if c in ['reserve','userReserveMode']:
                counts=values.value_counts()
                top=sorted(counts.index,key=lambda k:(-counts[k],k))[:10]
                values=values.where(values.isin(top),'Other')
                self.categories[c]=sorted(set(top)|{'Other'})
            else:
                self.categories[c]=sorted(set(values)|{'Other'})
        self.center=frame[self.numeric].mean()
        self.scale=frame[self.numeric].std(ddof=1)
        if self.scaling:
            self.numeric=[c for c in self.numeric if np.isfinite(self.scale[c]) and self.scale[c]>0]
        self.pca=None
        encoded=self._transform(frame)
        if self.pca_variance is not None:
            if not self.encoding: raise ValueError('PCA requires numeric encoding')
            from sklearn.decomposition import PCA
            self.pca=PCA(n_components=self.pca_variance,svd_solver='full').fit(encoded)
        return self

    def _transform(self, frame):
        result=frame[self.numeric].copy()
        if self.scaling: result=(result-self.center[self.numeric])/self.scale[self.numeric]
        for c, categories in self.categories.items():
            values=frame[c].astype('string').fillna('Other')
            values=values.where(values.isin(categories),'Other')
            if self.encoding:
                for category in categories[1:]: result[c+'_'+category]=values.eq(category).astype(float)
            else: result[c]=values
        return result

    def transform(self, frame):
        features=self._transform(frame)
        if self.pca is not None:
            features=pd.DataFrame(self.pca.transform(features),index=frame.index,
                                  columns=[f'PC{i+1}' for i in range(self.pca.n_components_)])
        return features,frame[TARGETS].copy(),frame[[c for c in IDENTITY if c in frame]].copy()


def classification_view(frame, cutoff_days):
    """R classification rule: omit censored before/equal horizon; seconds -> days."""
    if cutoff_days<=0: raise ValueError('Positive horizon required')
    df=frame[(frame.timeDiff>0)&~((frame.timeDiff/86400<=cutoff_days)&frame.status.eq(0))].copy()
    df['event']=np.where(df.timeDiff/86400<=cutoff_days,'yes','no')
    return df.drop(columns=TARGETS)
