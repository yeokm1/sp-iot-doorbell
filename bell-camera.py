import time
import requests
import os
import RPi.GPIO as GPIO
import _thread
import socket

from time import sleep

# Put your slack token here
#slack_token = os.environ["SLACK_API_TOKEN"]
slack_token = "xxxx"

channelID = "#doorbell"
botUserName = "bell-camera"

pathToImage = "/tmp/iot-doorbell-visitor.jpg"

#Rotate 270 as camera is placed at angle, 30% quality and 640x480 resolution to reduce file size
takePictureCommand = "/opt/vc/bin/raspistill -ISO 800 -ss 40000 -q 30 -rot 270 -t 1 -w 640 -h 480 -o " + pathToImage

buttonPin = 17
buzzerPin = 23

minimumSendSlackInterval = 10 #seconds
referenceServer = "slack.com"
maxInitialConnectionRetries = 20

isInternetActive = False

isSendingThreadActive = False
lastSentTime = time.time()


#Referenced from http://stackoverflow.com/questions/20913411/test-if-an-internet-connection-is-present-in-python
def isInternetON(referenceServer):
    try:
        host = socket.gethostbyname(referenceServer)
        s = socket.create_connection((host, 80), 2)
        return True
    except :
        return False

def takePicture():
    os.system(takePictureCommand)

def generateNewDisplayFilename():
    timestr = time.strftime("%Y-%m-%d-%H%M%S")
    displayFilename = timestr + ".jpg"
    return displayFilename

def sendMessage(message):
    postMessage(message, slack_token, channelID)

def postMessage(message, token, channel):
    try:
        response = requests.post(
        url ='https://slack.com/api/chat.postMessage',
        data = {
                'token': token,
                'as_user': False,
                'username': botUserName,
                'icon_emoji': ":bell:",
                'channel': channel,
                'link_names': 1,
                'text': message
                },
                headers = {'Accept': 'application/json'})
    except requests.exceptions.RequestException as e:
        print(e)
        return (e)

    return response.text


#Code referenced from http://stackoverflow.com/questions/37283111/cannot-post-images-to-slack-channel-via-web-hooks-utilizing-python-requests
def postImage(displayFilename, actualFilename, token, channels):

    imageFile = open(actualFilename, 'rb')

    f = {'file': (displayFilename, imageFile, 'image/jpg', {'Expires':'0'})}

    try:
        response = requests.post(
        url ='https://slack.com/api/files.upload',
        data = {
                'token': token,
                'channels': channels,
                'media': f
                },
        headers = {'Accept': 'application/json'}, files=f)
    except requests.exceptions.RequestException as e:
        print(e)
        return (e)

    imageFile.close()

    return response.text


def sendToSlackThread():
    global isSendingThreadActive

    if(isSendingThreadActive):
        return

    isSendingThreadActive = True

    print ("Taking picture")
    takePicture()

    print ("Sending first quick message")
    sendMessage("Visitor is @here!")

    print ("Uploading image")
    postImage(generateNewDisplayFilename(), pathToImage, slack_token, channelID)

    print ("Image upload attempt completed")

    isSendingThreadActive = False


GPIO.setmode(GPIO.BCM)
GPIO.setup(buttonPin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(buzzerPin, GPIO.OUT)


# One buzz to indicate program start
print ("Output initial buzzes")
GPIO.output(buzzerPin, 1)
sleep(0.3)
GPIO.output(buzzerPin, 0)
sleep(0.3)

#Loop until network connection is obtained, buzz a short while for each attempt
for x in range(0, maxInitialConnectionRetries):
    print("Trying to hit reference server " + referenceServer + " attempt " + str(x))
    GPIO.output(buzzerPin, 1)
    sleep(0.01)
    GPIO.output(buzzerPin, 0)

    if(isInternetON(referenceServer)):
        isInternetActive = True
        break

    sleep(1)

if(isInternetActive):
    print("Sending initial test message")
    sendMessage("Test message after boot")

    # Two buzzes to indicate test message was just sent
    GPIO.output(buzzerPin, 1)
    sleep(0.3)
    GPIO.output(buzzerPin, 0)
    sleep(0.3)
    GPIO.output(buzzerPin, 1)
    sleep(0.3)
    GPIO.output(buzzerPin, 0)
else:
    GPIO.output(buzzerPin, 1)
    sleep(0.3)
    GPIO.output(buzzerPin, 0)


print("Program active")

while True:
    sleep(0.1)

    buttonInput = GPIO.input(buttonPin)

    #Logic is inverted as the button is pull up
    if(buttonInput):
        GPIO.output(buzzerPin, 0)
    else:
        GPIO.output(buzzerPin, 1)

        currentTime = time.time()

        if(not isSendingThreadActive and (currentTime - lastSentTime) >= minimumSendSlackInterval):
            lastSentTime = currentTime
            _thread.start_new_thread(sendToSlackThread,())
