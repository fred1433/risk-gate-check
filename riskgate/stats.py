from math import comb
def _cdf(k,n,p): return sum(comb(n,i)*p**i*(1-p)**(n-i) for i in range(k+1))
def clopper_pearson(k,n,alpha=0.05):
    """Exact two-sided interval for a binomial proportion. Assumes independent cases (see limits)."""
    if n==0: return (0.0,1.0)
    def bisect(f,lo=0.0,hi=1.0):
        for _ in range(80):
            mid=(lo+hi)/2
            if f(mid): hi=mid
            else: lo=mid
        return (lo+hi)/2
    lower=0.0 if k==0 else bisect(lambda p: 1-_cdf(k-1,n,p) >= alpha/2)
    upper=1.0 if k==n else bisect(lambda p: _cdf(k,n,p) <= alpha/2)
    return (lower,upper)
