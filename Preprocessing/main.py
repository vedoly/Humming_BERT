import tkinter as tk
from tkinter import filedialog, ttk, StringVar
import pygame
import os
import _thread

import os
from musicautobot.numpy_encode import *
from musicautobot.config import *
from musicautobot.music_transformer import *
from musicautobot.multitask_transformer import *
from musicautobot.utils import midifile
from mido import MidiFile, MetaMessage
import time
import mido


# mixer config
freq = 44100  # audio CD quality
bitsize = -16   # unsigned 16 bit
channels = 2  # 1 is mono, 2 is stereo
buffer = 1024   # number of samples

########## ใส่โค้ดในนี้ได้ก็ดี ###########


def merge2(first,second):



    cv1 = MidiFile(first, clip=True)
    cv2 = MidiFile(second, clip=True)
    
    cv1.tracks.append(cv2.tracks[0])
    cv1.tracks.append(cv2.tracks[1])
    cv1.save('mashup.mid')

def seperateByBar(item,d):
    note = item.to_text().split(" ")
    beat = item.position
    out = []
    tmp = []
    current_beat = 0
    last_note = ''
    for i in range(len(note)):
        if(beat[i]//d == current_beat):
            if(len(tmp)==0):
                tmp.append(last_note)
            tmp.append(note[i])
        else:
            out.append(tmp)
            tmp = []
            last_note = note[i]
            while(current_beat  < (beat[i]//d) - 1):
                out.append([])
                current_beat+=1
            current_beat= beat[i]//d
    return out

def merge(first, second):
    mid1 = MidiFile(first)
    mid2 = MidiFile(second)
    output = MidiFile(ticks_per_beat=mid1.ticks_per_beat, clip=mid1.clip, charset=mid1.charset, type=mid1.type)

    for i, track in enumerate(mid2.tracks):
        new_msgs = []
        for j, msg in enumerate(mid2.tracks[i]):
            if "velocity" in msg.dict().keys():
                new_msgs.append(MetaMessage('text', **{'text': f'{{"{j}":{str(msg.velocity)}}}'}))
                msg.velocity = 0
        for msg in new_msgs:
            track.insert(len(track), msg)
        output.tracks.append(track)

    for i, track in enumerate(mid1.tracks):
        output.tracks.append(track)

    print(output.length)
    output.save(filename="merged.mid")
def clearExceed(arr):
    last_sep = 9999
    for i in range(len(arr)-1,-1,-1):
        if(arr[i]=='xxsep'):
            last_sep = i
            break
    return arr[:last_sep+2]

def countSep(arr):
    count = 0
    out = []
    for i in range(len(arr)):
        out.append(arr[i])
        if arr[i] == 'xxsep':
            count+= int(arr[i+1][1:])
        if count > 48:
            out.append(arr[i+1])
            break
    return out,count

def countSepNum(arr):
    count = 0
    out = []
    for i in range(len(arr)):
        out.append(arr[i])
        if arr[i] == 'xxsep':
            count+= int(arr[i+1][1:])
        if count >= 48:
            out.append(arr[i+1])
            break
    
    
    return count
def clearSep(x):
    if countSepNum(x) == 48:
        return x
    diff = 48 - countSepNum(x)
    last_sep = int(x[-1][1:])
    last_sep += diff
    assert last_sep > 0
    return x[:-1] + ['d' + str(last_sep)]

def testPredict(filename):

    rightpath = 'right/' + filename
    leftpath = 'left/' + filename
    resultpath = 'result/' + filename

    os.system('onmt_translate -model cp_step_18500.pt -src '+rightpath+' -output '+resultpath+' -verbose')
    time.sleep(1000)
    left = [ clearSep(countSep(clearExceed(e.strip().split(" ")))[0]) for e in open(resultpath).readlines()]
    right = [ e.strip().split(" ") for e in open(rightpath)]
    left_gt =[ e.strip().split(" ") for e in open(leftpath)]

    left_hand = []
    right_hand = []
    left_hand_gt = []
    for c in left:
        left_hand += c

    for c in right:
        right_hand += c

    for c in left_gt:
        left_hand_gt += c

    vocab = MusicVocab.create()
    stoi = vocab.stoi

    right_hand_test = ['xxbos','xxpad'] + right_hand
    right_hand_test = [stoi[e] for e in right_hand_test]

    left_hand_test = ['xxbos','xxpad'] + left_hand
    left_hand_test = [stoi[e] for e in left_hand_test]

    left_hand_gt_test = ['xxbos','xxpad'] + left_hand_gt
    left_hand_gt_test = [stoi[e] for e in left_hand_gt_test]

    right_hand_midi = idxenc2stream(np.array(right_hand_test),vocab)
    left_hand_midi = idxenc2stream(np.array(left_hand_test),vocab)
    left_hand_midi_gt = idxenc2stream(np.array(left_hand_gt_test),vocab)

    fp = right_hand_midi.write('midi', fp=filename+'_right.mid')
    fp = left_hand_midi.write('midi', fp=filename+'_left.mid')
    
    fp = left_hand_midi_gt.write('midi', fp=filename+'_left_gt.mid')


    

def clearBos(arr):

    return [arr[0][3:]]+arr[1:]

def desSep(arr,d):

    out = []
    remain = 0
    for j,c in enumerate(arr):
        

        tmp = []

        if remain > 0:
            tmp = ['xxsep'] + tmp
            tmp = tmp + ['d' + str(min(remain,d))] 
            remain -= d
            remain = max(0,remain)
        if len(c) == 0:
            out.append(tmp)
            continue

        count = 0
        c = tmp + c 
        last_sep = int( c[-1][1:] )
        for i in range(len(c[:-2])):
            try:
                if c[i] == 'xxsep':
                    count += int( c[i+1][1:] )
            except:
                pass
        new = d - count
        remain += last_sep - new
        if j==0 :
          tmp += c[0:-2] + ['xxsep'] + ['d' + str(new)]
        else:
          tmp += c[2:-2] + ['xxsep'] + ['d' + str(new)]
        out.append(tmp)
    return out

def predictMidi(filename):
    print(filename)
    vocab = MusicVocab.create()
    stoi = vocab.stoi

    item = MusicItem.from_file(filename, vocab)
    # s= item.to_text()
    # s = " ".join(s.split(' '))
    s = desSep(clearBos(seperateByBar(item,48)),48)
    s = [" ".join(e) for e in s]
    with open('tmp.txt', 'w') as f:
      for c in s:
          f.write("%s\n" % c)
    s = [e.split(' ') for e in s]
    os.system('onmt_translate -model cp_step_18500.pt -src tmp.txt -output pred.txt')
    time.sleep(2)
    
    left = [ clearSep(countSep(clearExceed(e.strip().split(" ")))[0]) for e in open('pred.txt').readlines()]
    right = s

    left_hand = []
    right_hand = []

    for c in left:
        left_hand += c

    for c in right:
        right_hand += c
    


    vocab = MusicVocab.create()
    stoi = vocab.stoi

    right_hand_test = ['xxbos','xxpad'] + right_hand
    right_hand_test = [stoi[e] for e in right_hand_test]

    left_hand_test = ['xxbos','xxpad'] + left_hand
    left_hand_test = [stoi[e] for e in left_hand_test]


    right_hand_midi = idxenc2stream(np.array(right_hand_test),vocab)
    left_hand_midi = idxenc2stream(np.array(left_hand_test),vocab)

    fp = right_hand_midi.write('midi', fp='tmp_right.mid')
    fp = left_hand_midi.write('midi', fp='tmp_left.mid')


    merge2('tmp_right.mid','tmp_left.mid')





























def doMlProcess(filePath):
    predictMidi(filePath)
    # return 'mashup.mid'
def play_music(midi_filename):
    clock = pygame.time.Clock()
    # LOAD MIDI IN STATIC PATH
    pygame.mixer.music.load(midi_filename)
    pygame.mixer.music.play()
    try:
        while pygame.mixer.music.get_busy():
            clock.tick(30) # check if playback has finished
    except KeyboardInterrupt:
        # if user hits Ctrl/C then exit
        # (works only in console mode)
        pygame.mixer.music.fadeout(1000)
        pygame.mixer.music.stop()
        raise SystemExit
    
def selectMidi():
    global midiFilePath
    midiFilePath = filedialog.askopenfilename(initialdir=os.getcwd(), title="Select midi file", filetypes=(("Midi", "*.mid"), ("Midi", "*.midi"),("all files", "*.*")))
    doMlProcess(midiFilePath)
    _thread.start_new_thread( play_music, ('mashup.mid',) )

############## MIDI MAGIC ##############
pygame.mixer.init(freq, bitsize, channels, buffer)
pygame.mixer.music.set_volume(1)
midiFilePath = ""

############### GUI #################
root = tk.Tk(className="NLP MIDI")
root.geometry("200x200")
root.resizable(0, 0)

inputBtn = tk.Frame(root)
inputBtn.pack(side="top", fill="x")
b_inpMidi = tk.Button(inputBtn,width="20", height="2", text="Select midi file", command=lambda:selectMidi())
b_inpMidi.pack(side='left', padx=(25,0))
# test.pack()
root.mainloop() 