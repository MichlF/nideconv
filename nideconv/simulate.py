import numpy as np
import pandas as pd
import scipy as sp
from scipy import signal
from .utils import convolve_with_function


def simulate_fmri_experiment(conditions=None,
                             TR=1.,
                             n_subjects=1, 
                             n_runs=1, 
                             n_trials=40, 
                             run_duration=300,
                             oversample=20,
                             n_rois=1,
                             kernel='double_gamma',
                             kernel_pars={}):
    """
    This function simulates an fMRI experiment. 
    
    The conditions-variable is a list of dictionaries, each including a mu_group and mu_std-field
    to indicate the mean impulse height, as well as the standard deviation across subjects.
    It also includes a n_trials-field to simulate the number of trials for that condition and
    potentially a 'name'-field to label the condition.
    The sd of the noise in the signal is always unity.
    """

    if kernel not in ['double_gamma', 'gamma']:
        raise NotImplementedError()
    
    data = []

    if conditions is None:
        conditions = [{'name':'A',
                       'mu_group':1,
                       'std_group':0,},
                       {'name':'B',
                       'mu_group':2,
                       'std_group':0}]
    
    conditions = pd.DataFrame(conditions).set_index('name')
    
    sample_rate = 1./TR
    
    frametimes = np.arange(0, run_duration, TR)
    all_onsets = []
    
    parameters = []
    for subject in np.arange(1, n_subjects+1):
        
        for i, condition in conditions.iterrows():
            amplitude = sp.stats.norm(loc=condition['mu_group'], scale=condition['std_group']).rvs()
            condition['amplitude'] = amplitude
            condition['subject'] = subject
            condition['trial_type'] = condition.name
            parameters.append(condition.drop(['mu_group', 'std_group'], axis=0))
            
    parameters = pd.DataFrame(parameters).set_index(['subject', 'trial_type'])

    if 'kernel' not in parameters.columns:
        parameters['kernel'] = kernel
    else:
        parameters['kernel'].fillna(kernel, inplace=True)

    if 'kernel_pars' not in parameters.columns:
        parameters['kernel_pars'] = np.nan

    if type(n_trials) is int:
        n_trials = [n_trials] * len(conditions)
    
    for subject in np.arange(1, n_subjects+1):
        
        for run in range(1, n_runs+1):
            
            signals = np.zeros((len(conditions), len(frametimes)))

            for i, (_, condition) in enumerate(conditions.iterrows()):
                if 'onsets' in condition:
                    onsets = np.array(condition.onsets)
                else:
                    onsets = np.ones(0)

                    while len(onsets) < n_trials[i]:
                        isis = np.random.gamma(run_duration / n_trials[i], 1, size=n_trials[i] * 10)
                        onsets = np.cumsum(isis)
                        onsets = onsets[onsets < run_duration]

                    onsets = np.random.choice(onsets, 
                                              n_trials[i],
                                              replace=False)

                signals[i, (onsets / TR).astype(int)] = parameters.loc[(subject, condition.name), 'amplitude']
                
                
                all_onsets.append(pd.DataFrame({'onset':onsets}))
                all_onsets[-1]['subject'] = subject
                all_onsets[-1]['run'] = run
                all_onsets[-1]['trial_type'] = condition.name

                kernel_pars = parameters.loc[(subject, condition.name), 'kernel_pars']
                if type(kernel_pars) is not dict:
                    kernel_pars = {}

                print(kernel_pars)
                signals[i] = convolve_with_function(signals[i],
                                                    parameters.loc[(subject, condition.name), 'kernel'],
                                                    sample_rate,
                                                    **kernel_pars)

                
                
            signal = signals.sum(0)
            signal = np.repeat(signal[:, np.newaxis], n_rois, 1)
            signal += np.random.randn(*signal.shape)
            
            if n_rois == 1:
                columns = ['signal']
            else:
                columns = ['area %d' % i for i in range(1, n_rois + 1)]

            tmp = pd.DataFrame(signal,
                               columns=columns)

            tmp['t'] = frametimes
            tmp['subject'], tmp['run'] = subject, run
                
            data.append(tmp)
            
    data = pd.concat(data).set_index(['subject', 'run', 't'])
    onsets = pd.concat(all_onsets).set_index(['subject', 'run', 'trial_type'])
    
    if n_subjects == 1:
        data.index = data.index.droplevel('subject')
        onsets.index = onsets.index.droplevel('subject')

    if n_runs == 1:
        data.index = data.index.droplevel('run')
        onsets.index = onsets.index.droplevel('run')

    
    return data, onsets, parameters

