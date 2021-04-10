"""
Interface for blender rendering of images
@author: Ken Campbell
"""

import os
import json
import subprocess

import threading
import multiprocessing
import time

from pathlib import Path

from .movie_with_data import movie_with_data

def generate_images(render_batch_file):
    """ Function generates images defined by a template file
        for every frame defined in a frames file
        using options defined in a blender file
        
        Multiple frames are generated by multithreading a single call
        that passes the tempate information, the blender information
        and data for a single frame to generate2.py """

    # Load the render batch file as a dict
    with open(render_batch_file, 'r') as f:
        render_batch = json.load(f)
    
    render_jobs = render_batch['render_batch']['render_jobs']
    # In principle, you can run multiple jobs in sequence so
    # loop through them

    jobs = render_jobs
    for rj in jobs:

        # Generate single frame dicts as an array
        if (rj['relative_to'] == 'this_file'):
            parent_path = Path(render_batch_file).parent
            frames_file = os.path.abspath(
                os.path.join(parent_path, rj['frames_file']))
            template_file = os.path.join(parent_path, rj['template_file'])
            blender_file = os.path.join(parent_path, rj['blender_file'])

        with open(frames_file, 'r') as f:
            frames_data = json.load(f)
        
        job_files = []
        for i, frame in enumerate(frames_data['frames']):
            # Write the frame data to a temp file

            # Adjust the files for the temp path
            frame['status_file'] = os.path.join('..',
                                                frame['status_file'])
            frame['image_file'] = os.path.join('..',
                                               frame['image_file'])
            
            # Make sure temp dir exists
            temp_dir = os.path.join(parent_path, 'temp')
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)
            temp_frame_file = os.path.join(temp_dir,
                                           'frame_%i.json' % i)

            # Get frame infomration into consistent format
            frame_data=dict()
            frame_data['frame_data'] = frame

            # Write to file
            with open(temp_frame_file, 'w') as f:
                json.dump(frame_data, f, indent=4)

            job=dict()
            job['relative_to'] = 'this_file'
            job['job_number'] = i
            job['frame_file'] = 'frame_%i.json' % i
            job['template_file'] = os.path.join('..', rj['template_file'])
            job['blender_file'] = os.path.join('..', rj['blender_file'])
            
            render_job = dict()
            render_job['render_job'] = job
            
            job_file = os.path.join(temp_dir, 'job_%i.json' % i)
            with open(job_file, 'w') as f:
                json.dump(render_job, f, indent=4)
            
            job_files.append(job_file)

    # Now run the batches using all but one cpu
    num_processes = (multiprocessing.cpu_count() - 1)
    
    threads = []
    while threads or job_files:
        if (len(threads) < num_processes) and job_files:
            t = threading.Thread(target=worker,
                                  args=[job_files.pop()])
            t.setDaemon(True)
            t.start()
            threads.append(t)
        else:
            for thread in threads:
                if not thread.isAlive():
                    threads.remove(thread)

    return

def worker(render_file):
    # Renders a snapshot
    
    # Import the render data
    with open(render_file, 'r') as f:
        render_struct = json.load(f)
    render_job = render_struct['render_job']

    if (render_job['relative_to'] == 'this_file'):
        parent_path = Path(render_file).parent
        blender_file = os.path.join(parent_path,
                                    render_job['blender_file'])

        with open(blender_file, 'r') as f:
            blender_data = json.load(f)
    
        # Find the blender executable
        blender_exe_path = blender_data['blender_data']['blender_exe_path']
    
        # Generate the command string
        command_string = ('cd "%s"\n ' % blender_exe_path)
    
        # Deduce the path to this folder
        parent_path = Path(__file__).parent
        
        # Set path to generate.py
        generate_path = os.path.join(parent_path, 'generate2.py')
        
        # Add in background mode
        if (blender_data['blender_data']['background_mode']):
            background_string = '--background'
        else:
            background_string = ''
    
        # Complete the commmand line
        command_string = command_string + \
              ('blender -noaudio %s --python "%s" -- -j %s' %
                  (background_string,
                   generate_path,
                   os.path.abspath(render_file)))
        
        print(command_string)
        
        # # Write command to temp.bat
        bat_file_string = 'run_job_%i.bat' % render_job['job_number']
        print(bat_file_string)
        
        with open(bat_file_string, 'w') as f:
            f.write('%s' % command_string)
            f.close()
        
        subprocess.call(bat_file_string)
        time.sleep(1)
        try:
            os.remove(bat_file_string)
            print('deleted %s' % bat_file_string)
        except:
            print('No file to delete')
    
        return
