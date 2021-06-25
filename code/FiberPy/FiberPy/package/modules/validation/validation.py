import os, sys
import json

# Add the validation package

ROOT = os.path.dirname(__file__)
MODULES_ROOT = os.path.realpath(os.path.join(ROOT, "..", ".."))
sys.path.append(MODULES_ROOT)

from modules.validation import myosin_kinetics
from modules.validation import mybpc_kinetics
from modules.validation import actin_kinetics


def run_validation(kinetic_data, batch_file_string):
    """Entrance function for the FiberSim testing suite"""
    
    print("Run_validation starting")
    
    # Get the model/option/protocol file and output folder 
    
    base_folder = os.path.dirname(batch_file_string)
    
    if (kinetic_data['relative_to'] == 'this_file'):
        
        model_file = os.path.join(base_folder, kinetic_data['model_file'])
        
        protocol_file = os.path.join(base_folder, kinetic_data['protocol_file'])
        
        options_file = os.path.join(base_folder, kinetic_data['options_file'])
        
        output_folder = os.path.join(base_folder, kinetic_data['output_data_folder'])
        
    else:
        
        model_file = kinetic_data['model_file']
        protocol_file = kinetic_data['protocol_file']
        options_file = kinetic_data['options_file']
        output_folder = kinetic_data['output_data_folder']
        
    # Creatte output folder if it does not exist

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)    
        
    # Get dump_folder from option file
    
    with open(options_file, 'r') as f:
        opt = json.load(f)
    
    base_folder = os.path.dirname(options_file)
    
    if 'status_files' in opt['options']:
        if opt['options']['status_files']['relative_to'] == 'this_file':
            dump_folder = os.path.join(base_folder, opt['options']['status_files']['status_folder'])
        else:
            dump_folder = opt['options']['status_files']['status_folder']
            
    else:
        raise RuntimeError("No dump folder found to run the test")
        
    # Get number of adjacent bs from option file
    
    if 'adjacent_bs' in opt['options']:
        adj_bs = opt["options"]["adjacent_bs"]        
    else:
        adj_bs = 0
    
    # Now run the kinetics test or force-balance test
    
    val_type = kinetic_data["validation_type"]
    
    if (val_type == 'm_kinetics'): 
        
        print("Myosin kinetics check")
        
        myosin_kinetics.compute_rate(model_file, protocol_file, dump_folder, output_folder, adj_bs)
        
    if (val_type == 'c_kinetics'): 
              
        print("Mybpc kinetics check")
        
        mybpc_kinetics.compute_rate(model_file, protocol_file, dump_folder, output_folder, adj_bs)
        
    if (val_type == 'a_kinetics'): 
                
        print("Actin kinetics check")
        
        actin_kinetics.compute_rate(model_file, protocol_file, dump_folder, output_folder)   
        
        