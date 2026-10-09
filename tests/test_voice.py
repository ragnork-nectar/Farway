import pyttsx3

# Test 1: Fresh engine, default voice
print("Test 1: Default voice")
e1 = pyttsx3.init("sapi5")
e1.say("Test one. Default voice.")
e1.runAndWait()
e1.stop()

# Test 2: Male voice (David)
print("Test 2: Male voice David")
e2 = pyttsx3.init("sapi5")
for v in e2.getProperty("voices"):
    if "david" in v.name.lower():
        e2.setProperty("voice", v.id)
        print(f"Using: {v.name}")
        break
e2.say("Test two. Male voice working.")
e2.runAndWait()
e2.stop()

# Test 3: Repeat call (ye kabhi fail hoti thi)
print("Test 3: Second call same session")
e3 = pyttsx3.init("sapi5")
e3.say("Test three. Should work.")
e3.runAndWait()
e3.stop()

print("Done!")