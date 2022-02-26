# -*- coding: utf-8 -*-
"""
Created on Tue Feb 15 12:47:26 2022

@author: kscamp3
"""
import os
import json
import shutil

import numpy as np
import pandas as pd

from pathlib import Path

from ..protocols import protocols as prot
from ..batch import batch

def characterize_model(json_analysis_file_string):
    """ Code takes a json struct that includes a model file, and run the
        analyses described in the file """
        
    # Check for the analysis file
    if (not json_analysis_file_string):
        print('deduce_fv_properties: no analysis file specified')
        exit(1)
    
    # Load it
    with open(json_analysis_file_string, 'r') as f:
        json_data = json.load(f)
        anal_struct = json_data['FiberSim_analysis']
   
    # Pull of the analysis tasks
    anal_struct = anal_struct['analysis']
    for an in anal_struct:
        if (an['type'] == 'pCa_length_control'):
            deduce_pCa_length_control_properties(json_analysis_file_string,
                                                 pCa_struct = an)
        if (an['type'] == 'force_velocity'):
            deduce_fv_properties(json_analysis_file_string,
                                 fv_struct = an)
            
def deduce_pCa_length_control_properties(json_analysis_file_string,
                                         pCa_struct = []):
    """ Code runs pCa analysis """

    # Potentially switch off simulations
    figures_only = False
    if ('figures_only' in pCa_struct):
        if (pCa_struct['figures_only'] == "True"):
            figures_only = True
    
    # Load the file
    with open(json_analysis_file_string, 'r') as f:
        json_data = json.load(f)
        anal_struct = json_data['FiberSim_analysis']
    
    # Pull off the components
    FiberCpp_exe_struct = anal_struct['FiberCpp_exe']
    model_struct = anal_struct['model']
    
    # Create an isometric batch to run the isomtric test
    pCa_lc_b = dict()
    
    # Turn the FiberCpp_exe into absolute paths because the new instruction
    # file will be in a different place
    if (FiberCpp_exe_struct['relative_to'] == 'this_file'):
        base_dir = Path(json_analysis_file_string).parent.absolute()
        FiberCpp_exe_struct['relative_to'] = 'False'
        FiberCpp_exe_struct['exe_file'] = \
            os.path.join(base_dir, FiberCpp_exe_struct['exe_file'])
        pCa_lc_b['FiberCpp_exe'] = FiberCpp_exe_struct

    pCa_lc_b['job'] = []
    
    # Loop through the model files
    for i, mod_f in enumerate(model_struct['model_files']):
        
        # Create a folder for the sim_input
        if (pCa_struct['relative_to'] == 'this_file'):
            base_dir = Path(json_analysis_file_string).parent.absolute()
            sim_input_dir = os.path.join(base_dir,
                                         pCa_struct['sim_folder'],
                                         'sim_input',
                                         ('%i' % (i+1)))
            if not os.path.isdir(sim_input_dir):
                os.makedirs(sim_input_dir)
           
        # Copy the model and options files to the sim_input dir
        if (model_struct['relative_to'] == 'this_file'):
            base_dir = Path(json_analysis_file_string).parent.absolute()
            
            orig_model_file = os.path.join(base_dir, mod_f)
            fn = orig_model_file.split('/')[-1]
            iso_model_file = os.path.join(sim_input_dir, fn)
            shutil.copyfile(orig_model_file, iso_model_file)
            
            orig_options_file = os.path.join(base_dir, model_struct['options_file'])
            fn = orig_options_file.split(os.sep)[-1]
            iso_options_file = os.path.join(sim_input_dir, fn)
            shutil.copyfile(orig_options_file, iso_options_file)
       
        # Loop through the pCa values
        for pCa_counter,pCa in enumerate(pCa_struct['pCa_values']):
            
            if (pCa_counter==0):
                # Update the options file to dump rates
                with open(iso_options_file, 'r') as f:
                    json_data = json.load(f)
                    json_data['options']['rate_files'] = dict()
                    json_data['options']['rate_files']['relative_to'] = 'this_file'
                    json_data['options']['rate_files']['file'] = \
                        os.path.join('../../sim_output',
                                     ('%i' % (i+1)),
                                     'rates.txt')
                iso_options_file_rates = os.path.join(
                    Path(iso_options_file).parent.absolute(),
                    'sim_options_rates.json')

                with open(iso_options_file_rates, 'w') as f:
                    json.dump(json_data, f, indent=4)
            
            # Set the delta_hsl vector
            n_points = int(pCa_struct['sim_duration_s'] /
                           pCa_struct['time_step_s'])
            delta_hsl = np.zeros(n_points)
            mode_vector = -2 * np.ones(n_points)
            
            # Add in k_tr if required
            if ('k_tr_start_s' in pCa_struct):
                # Calculate some stuff for the k_tr
                k_tr_start_ind = int(pCa_struct['k_tr_start_s'] /
                                     pCa_struct['time_step_s'])
                k_tr_stop_ind = int((pCa_struct['k_tr_start_s'] + 
                                         pCa_struct['k_tr_duration_s']) /
                                    pCa_struct['time_step_s'])
                k_tr_ramp_points = int(pCa_struct['k_tr_ramp_s'] /
                                       pCa_struct['time_step_s'])
                ramp_inc = pCa_struct['k_tr_magnitude_nm'] / \
                                float(k_tr_ramp_points)
                # Set the k_tr_shortening
                vi = np.arange(k_tr_start_ind,
                               k_tr_start_ind + k_tr_ramp_points, 1)
                delta_hsl[vi] = -ramp_inc
                # Set the k_tr_re-stretch
                vi = np.arange(k_tr_stop_ind,
                               k_tr_stop_ind + k_tr_ramp_points, 1)
                delta_hsl[vi] = ramp_inc
                # Set the mode
                vi = np.arange(k_tr_start_ind,
                               k_tr_stop_ind + k_tr_ramp_points, 1)
                mode_vector[vi] = -1
                
            # Create a length control protocol and write to file
            df = prot.create_length_control_protocol(
                    time_step = pCa_struct['time_step_s'],
                    step_pCa = pCa,
                    n_points = n_points,
                    delta_hsl = delta_hsl,
                    mode_vector = mode_vector)
            prot_file_string = os.path.join(sim_input_dir,
                                            'prot_pCa_%.0f.txt' % (10*pCa))
            prot.write_protocol_to_file(df, prot_file_string)
            
            # Create the job
            j = dict()
            j['relative_to'] = 'False'
            j['protocol_file'] = prot_file_string
            j['results_file'] = os.path.join(base_dir,
                                             pCa_struct['sim_folder'],
                                             'sim_output',
                                             ('%i' % (i+1)),
                                             'sim_pCa_%.0f.txt' % (10*pCa))
            j['model_file'] = iso_model_file
            if (pCa_counter == 0):
                j['options_file'] = iso_options_file_rates
            else:
                j['options_file'] = iso_options_file
            
            # Create the structure for the output handler
            oh = dict()
            oh['templated_images'] = []
            tf = dict()
            tf['relative_to'] = 'this_file'
            tf['template_file_string'] = os.path.join(
                                            '..',
                                            base_dir,
                                            'template',
                                            'template_summary.json')
            tf['output_file_string'] = os.path.join(
                                            base_dir,
                                            pCa_struct['sim_folder'],
                                            'sim_output',
                                            ('%i' % (i+1)),
                                            'sim_pCa_%.0f.png' % (10*pCa))
            oh['templated_images'].append(tf)
            
            # Now add it to the job, and write it to file
            j['output_handler_file'] = os.path.join(
                                        sim_input_dir,
                                        'output_handler_pCa_%.0f.json' %
                                            (10*pCa))
            
            with open(j['output_handler_file'], 'w') as f:
                json.dump(oh, f, indent=4)        
        
            pCa_lc_b['job'].append(j)
    
    # Now create the analysis section
    batch_figs = dict()

    # pCa curves
    batch_figs['pCa_curves'] = []
    fig = dict()
    fig['relative_to'] = "False"
    fig['results_folder'] = os.path.join(base_dir,
                                          pCa_struct['sim_folder'],
                                          'sim_output')
    fig['data_field'] = 'force'
    fig['output_data_file_string'] = os.path.join(base_dir,
                                                  pCa_struct['sim_folder'],
                                                  'sim_output',
                                                  'pCa_analysis.xlsx')
    fig['output_image_file'] = os.path.join(base_dir,
                                                   pCa_struct['sim_folder'],
                                                   'sim_output',
                                                   'force_pCa')
    fig['output_image_formats'] = pCa_struct['output_image_formats']
    fig['formatting'] = dict()
    fig['formatting']['y_axis_label'] = 'Force (N m$^{\\mathregular{-2}}$)'
    batch_figs['pCa_curves'].append(fig)

    # Rates
    batch_figs['rates'] = []
    fig = dict()
    fig['relative_to'] = "False"
    fig['results_folder'] = os.path.join(base_dir,
                                         pCa_struct['sim_folder'],
                                         'sim_output')
    fig['output_image_file'] = os.path.join(base_dir,
                                            pCa_struct['sim_folder'],
                                            'sim_output',
                                            'rates')
    fig['output_image_formats'] = pCa_struct['output_image_formats']
    batch_figs['rates'].append(fig)
    
    pCa_lc_b['batch_figures'] = batch_figs
    
    # Now insert isometric_b into a full batch structure
    pCa_lc_batch = dict()
    pCa_lc_batch['FiberSim_batch'] = pCa_lc_b

    
    # Write the batch to file
    base_dir = Path(json_analysis_file_string).parent.absolute()
    pCa_lc_batch_file = os.path.join(base_dir,
                                     pCa_struct['sim_folder'],
                                     'batch_isometric.json')
    with open(pCa_lc_batch_file, 'w') as f:
        json.dump(pCa_lc_batch, f, indent=4)
        
    # Now run the isometric batch
    batch.run_batch(pCa_lc_batch_file, figures_only=figures_only)
    

def deduce_fv_properties(json_analysis_file_string,
                         fv_struct = []):
    """ Code runs force-velocity analysis """

    # Potentially switch off simulations
    figures_only = False
    if ('figures_only' in fv_struct):
        if (fv_struct['figures_only'] == "True"):
            figures_only = True
            
    # Load the file
    with open(json_analysis_file_string, 'r') as f:
        json_data = json.load(f)
        anal_struct = json_data['FiberSim_analysis']
    
    # Pull off the components
    FiberCpp_exe_struct = anal_struct['FiberCpp_exe']
    model_struct = anal_struct['model']

    # First create a batch to run an isometric test. We use this to
    # get the force values for the fv tests

    # Create the isometric batch
    isometric_b = dict()
    
    # Turn the FiberCpp_exe into absolute paths because the new instruction file
    # will be in a different place
    if (FiberCpp_exe_struct['relative_to'] == 'this_file'):
        base_dir = Path(json_analysis_file_string).parent.absolute()
        FiberCpp_exe_struct['relative_to'] = 'False'
        FiberCpp_exe_struct['exe_file'] = \
            os.path.join(base_dir, FiberCpp_exe_struct['exe_file'])
    isometric_b['FiberCpp_exe'] = FiberCpp_exe_struct

    isometric_b['job'] = []

    # Loop through the model files
    for i, mod_f in enumerate(model_struct['model_files']):

        # Create a folder for the sim_input
        if (fv_struct['relative_to'] == 'this_file'):
            base_dir = Path(json_analysis_file_string).parent.absolute()
            sim_input_dir = os.path.join(base_dir, fv_struct['sim_folder'],
                                         'isometric', 'sim_input',
                                         ('%i' % (i+1)))
            if not os.path.isdir(sim_input_dir):
                os.makedirs(sim_input_dir)
            
        # Copy the model and options files to the sim_input dir
        if (model_struct['relative_to'] == 'this_file'):
            base_dir = Path(json_analysis_file_string).parent.absolute()
            
            orig_model_file = os.path.join(base_dir, mod_f)
            fn = orig_model_file.split('/')[-1]
            iso_model_file = os.path.join(sim_input_dir, fn)
            shutil.copyfile(orig_model_file, iso_model_file)
            
            orig_options_file = os.path.join(base_dir, model_struct['options_file'])
            fn = orig_options_file.split(os.sep)[-1]
            iso_options_file = os.path.join(sim_input_dir, fn)
            shutil.copyfile(orig_options_file, iso_options_file)
            
        
            # Create a length control protocol and write it to file
            df = prot.create_length_control_protocol(
                                    time_step = fv_struct['time_step_s'],
                                    step_pCa = fv_struct['pCa'],
                                    n_points = int(fv_struct['sim_duration_s'] /
                                                        fv_struct['time_step_s']))
            prot_file_string = os.path.join(sim_input_dir,
                                            'prot_iso_pCa_%.0f.txt' % (10 * fv_struct['pCa']))
            prot.write_protocol_to_file(df, prot_file_string);
 
        j = dict()
        j['relative_to'] = 'False'
        j['protocol_file'] = prot_file_string
        j['results_file'] = os.path.join(base_dir, fv_struct['sim_folder'],
                                         'isometric', 'sim_output',
                                         ('%i' % (i+1)),
                                         'sim_pCa_%.0f.txt' % (10 * fv_struct['pCa']))
        j['model_file'] = iso_model_file
        j['options_file'] = iso_options_file
        
        # Create the structure for the output handler
        oh = dict()
        oh['templated_images'] = []
        tf = dict()
        tf['relative_to'] = 'this_file'
        tf['template_file_string'] = os.path.join(
                                        '..',
                                        base_dir,
                                        'template',
                                        'template_summary.json')
        tf['output_file_string'] = os.path.join(
                                        base_dir, fv_struct['sim_folder'],
                                        'isometric', 'sim_output',
                                        ('%i' % (i+1)),
                                        'sim_pCa_%.0f.png' % (10 * fv_struct['pCa']))
        oh['templated_images'].append(tf)
        
        # Now add it to the job, and write it to file
        j['output_handler_file'] = os.path.join(
                                    sim_input_dir,
                                    'output_handler_iso_pCa_%.0f.json' %
                                        (10 * fv_struct['pCa']))
        
        with open(j['output_handler_file'], 'w') as f:
            json.dump(oh, f, indent=4)        
    
        isometric_b['job'].append(j)
    
    # Now insert iso_b into a full batch structure
    isometric_batch = dict()
    isometric_batch['FiberSim_batch'] = isometric_b    
    
    # Write the batch to file
    base_dir = Path(json_analysis_file_string).parent.absolute()
    isometric_batch_file = os.path.join(base_dir, fv_struct['sim_folder'],
                                        'isometric',
                                        'batch_isometric.json')
    with open(isometric_batch_file, 'w') as f:
        json.dump(isometric_batch, f, indent=4)
        
    # Now run the isometric batch
    batch.run_batch(isometric_batch_file, figures_only=figures_only)

    # Switch to isotonic stuff
    # First create the isotonic batch dict
    isotonic_b = dict()
    isotonic_b['FiberCpp_exe'] = FiberCpp_exe_struct
    isotonic_b['job'] = []
    
    # Now cycle thought the isometric jobs, generating an isotonic suite
    # for each one
    for (i,r) in enumerate(isometric_batch['FiberSim_batch']['job']):

        # Pull off the isometric force
        sim_data = pd.read_csv(r['results_file'], sep='\t')
        isometric_force = sim_data['force'].iloc[-1]

        # Deduce the sim input dir
        base_dir = Path(json_analysis_file_string).parent.absolute()
        sim_input_dir = os.path.join(base_dir, fv_struct['sim_folder'],
                                     'isotonic', 'sim_input',
                                     ('%i' % (i+1)))
        # Make it if required
        if not os.path.isdir(sim_input_dir):
            os.makedirs(sim_input_dir)
        
        orig_model_file = r['model_file']
        fn = orig_model_file.split('\\')[-1]
        isotonic_model_file = os.path.join(sim_input_dir, fn)
        shutil.copyfile(orig_model_file, isotonic_model_file)
        
        orig_options_file = r['options_file']
        fn = orig_options_file.split('\\')[-1]
        isotonic_options_file = os.path.join(sim_input_dir, fn)
        shutil.copyfile(orig_options_file, isotonic_options_file)

        # Cycle through the isotonic forces

        for (k, rel_f) in enumerate(fv_struct['rel_isotonic_forces']):
            j = dict()
            j['relative_to'] = 'False'
            j['model_file'] = isotonic_model_file
            j['options_file'] = isotonic_options_file
            prot_file_string = os.path.join(sim_input_dir,
                                      ('prot_%i.txt' % (k+1)))
            df = prot.create_force_control_protocol(
                                    time_step = fv_struct['time_step_s'],
                                    step_pCa = fv_struct['pCa'],
                                    n_points = int(fv_struct['sim_duration_s'] /
                                                        fv_struct['time_step_s']),
                                    iso_start_s = fv_struct['sim_release_s'],
                                    iso_f = rel_f * isometric_force)
            prot.write_protocol_to_file(df, prot_file_string);
            j['protocol_file'] = prot_file_string
            j['results_file'] = os.path.join(base_dir, fv_struct['sim_folder'],
                                              'isotonic', 'sim_output',
                                              ('%i' % (i+1)),
                                              ('sim_%i.txt' % (k+1)))
            
             # Create the structure for the output handler
            oh = dict()
            oh['templated_images'] = []
            tf = dict()
            tf['relative_to'] = 'this_file'
            tf['template_file_string'] = os.path.join(
                                            '..',
                                            base_dir,
                                            'template',
                                            'template_summary.json')
            tf['output_file_string'] = os.path.join(
                                            base_dir, fv_struct['sim_folder'],
                                            'isotonic', 'sim_output',
                                            ('%i' % (i+1)),
                                            ('sim_%i.png' % (k+1)))
            oh['templated_images'].append(tf)
        
            # Now add it to the job, and write it to file
            j['output_handler_file'] = os.path.join(
                                        base_dir, fv_struct['sim_folder'],
                                        'isotonic', 'sim_input',
                                        ('%i' % (i+1)),
                                        ('output_handler_sim_%i.json' % (k+1)))
        
            with open(j['output_handler_file'], 'w') as f:
                json.dump(oh, f, indent=4)      
            
            isotonic_b['job'].append(j)
        
    # Now create the batch analysis section
    batch_figs = dict()
    batch_figs['force_velocity'] = []
    fig = dict()
    fig['relative_to'] = "False"
    fig['results_folder'] = os.path.join(base_dir,
                                          fv_struct['sim_folder'],
                                          'isotonic',
                                          'sim_output')
    fig['fit_time_interval_s'] = fv_struct['fit_time_s']
    fig['output_data_file_string'] = os.path.join(base_dir,
                                                  fv_struct['sim_folder'],
                                                  'isotonic',
                                                  'sim_output',
                                                  'fv_analysis.xlsx')
    fig['output_image_file'] = os.path.join(base_dir,
                                            fv_struct['sim_folder'],
                                            'isotonic',
                                            'sim_output',
                                            'fv_and_power')
    fig['output_image_formats'] = fv_struct['output_image_formats']
    
    batch_figs['force_velocity'].append(fig)
    isotonic_b['batch_figures'] = batch_figs
    
    # Now insert isotonic_b into a full batch structure
    isotonic_batch = dict()
    isotonic_batch['FiberSim_batch'] = isotonic_b

    base_dir = Path(json_analysis_file_string).parent.absolute()
    isotonic_batch_file = os.path.join(base_dir, fv_struct['sim_folder'],
                                        'isotonic',
                                        'batch_isotonic.json')
    
    with open(isotonic_batch_file, 'w') as f:
        json.dump(isotonic_batch, f, indent=4)
        
    # Now run the isotonic batch
    batch.run_batch(isotonic_batch_file, figures_only=figures_only)
    