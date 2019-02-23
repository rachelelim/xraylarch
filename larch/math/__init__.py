

from .utils import (linregress, polyfit, realimag, as_ndarray,
                    complex_phase, deriv, interp, interp1d,
                    remove_dups, remove_nans2, index_of,
                    index_nearest, savitzky_golay, smooth, boxcar)

from .lineshapes import (gaussian, lorentzian, voigt, pvoigt, hypermet,
                         pearson7, lognormal, gammaln,
                         breit_wigner, damped_oscillator,
                         expgaussian, donaich, skewed_voigt,
                         students_t, logistic, erf, erfc, wofz)


from .fitpeak import fit_peak
from .convolution1D import glinbroad
from .lincombo_fitting import lincombo_fit, lincombo_fitall
from .pca import pca_train, pca_fit
from .gridxyz import gridxyz

__toadd__ = {'_math', dict(linregress=linregress,
                           polyfit=polyfit,
                           realimag=realimag,
                           as_ndarray=as_ndarray,
                           complex_phase=complex_phase,
                           deriv=deriv,
                           interp=interp,
                           interp1d=interp1d,
                           remove_dups=remove_dups,
                           remove_nans2=remove_nans2,
                           index_of=index_of,
                           index_nearest=index_nearest,
                           savitzky_golay=savitzky_golay,
                           smooth=smooth,
                           boxcar=boxcar,
                           glinbroad=glinbroad,
                           gridxyz=gridxyz,
                           fit_peak=fit_peak,
                          )}
