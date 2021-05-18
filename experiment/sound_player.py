import time
import random
import pyaudio
import wave
import csv
import pickle
import threading
import os
import numpy as np
import struct
import pandas as pd

class SoundPlayer(threading.Thread):
	def __init__(self,date,config_file):
		threading.Thread.__init__(self)
		
		self.terminated = False 
		self.date = date
		
		# read parameters in config files	
		parameters={}
		exec(open(config_file).read(),parameters)
		pars = parameters['params']
		self.period = pars['period']
		n_repeats= pars['n_repeats']
		
		# create sound list 
		# filter sounds from dataset
		sounds_df = pd.read_csv(pars['sound_list'], index_col=0)
		self.sounds_df = sounds_df[(sounds_df.octave.isin(pars['octaves'])) & (sounds_df.origin.isin(pars['types']))]
		# select random n_trials
		sound_list = list(self.sounds_df.file)
		n_sounds = len(sound_list)
		n_trials = pars['n_trials']
		sound_list = sound_list * int(np.ceil(n_trials/n_sounds)) # if less sounds than trials, duplicate
		random.shuffle(sound_list)
		sound_list = np.repeat(sound_list,n_repeats)
		print (sound_list)
		self.sound_list = sound_list[:n_trials]



	def set_participant(self, participant): 
		self.participant = participant

	def set_start_time(self,start_time):
		self.start_time = start_time


	def play_audio_callback(self,in_data, frame_count, time_info,status):
		
		# read frames from all files currently playing
		compteur=0
		delete_list = []
		data = np.zeros(frame_count).astype(np.int16)

		for index,file in enumerate(self.currently_playing):
			# read frames
			compteur+=1
			read_frame = file.readframes(frame_count)
			current_data=np.fromstring(read_frame,np.int16)
			
			# Uptade of 'compteur' for the late multiplication
			if current_data.size == 0:
				delete_list.append(index)
				compteur-=1

			# selection of only the non finished files left to play
			else :
				self.data_added=current_data

				# cases where sizes differ from file to file
				# if self.data_added.size>data.size:
				# 	rest = self.data_added.size-data.size
				# 	for index in range(rest):
				# 		data = np.append(data,0)

				if self.data_added.size<data.size:
					rest = data.size-self.data_added.size
					for index in range(rest):
						self.data_added = np.append(self.data_added,0)
				
				# overlap to buffer
				data += self.data_added

		for index in delete_list :
			del self.currently_playing[index]

		# print ('compteur ' + str(compteur))

		# multiplication to prevent the coded data to produce overflow error
		data = (data).astype(np.int16)

		return (data.tostring(), pyaudio.paContinue)
	
	
	def run(self):
		
		# Prepare csv for logging times  
		self.planning_file="data/treadmill_"+self.participant+'_'+str(self.date)+"_sound.csv"
		with open(self.planning_file, 'a') as file :
				writer = csv.writer(file,lineterminator='\n')
				header = ['time','sound_played','origin', 'note', 'octave', 'dynamics', 'pitch','shift']
				writer.writerow(header)

		
		self.start_time=time.time()
		self.current_time=time.time()


		# Create and start audio thread	
		audio = pyaudio.PyAudio()		
		self.wf= wave.open("sounds/"+self.sound_list[0]) # BUG IF SOUND LIST IS EMPTY

		self.output_stream = audio.open(format = audio.get_format_from_width(self.wf.getsampwidth()),
						channels = self.wf.getnchannels(),
						rate = self.wf.getframerate(),
						output = True, 
						stream_callback = self.play_audio_callback)

		self.output_stream.start_stream()


		# Put files in queue
		self.currently_playing = []
		for file in self.sound_list: 

			if self.terminated==True:
				self.output_stream.stop_stream()
				self.output_stream.close()
				audio.terminate()
				break
			# put file in queue
			self.currently_playing.append(wave.open("sounds/"+file))
			# retrieve metadata for file
			[origin,note,octave,dynamics,pitch,shift] = list(self.sounds_df[self.sounds_df.file==file][['origin','note','octave','dynamics','pitch','shift']].iloc[0])
			# write play time in trial file
			with open(self.planning_file, 'a') as data_file :
				writer = csv.writer(data_file,lineterminator='\n')
				writer.writerow([time.time()-self.start_time,
								file, origin, note, octave, dynamics, pitch,shift])
			
			time.sleep(self.period)


	def stop_playing(self):
		self.terminated = True