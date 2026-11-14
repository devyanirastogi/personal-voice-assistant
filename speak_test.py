import time
import speech

speech.speak("Your dentist appointment is booked for tomorrow at 3 PM in Chicago. "
             "The id is one. Have a nice day.")
time.sleep(3)                                # Give it time to start, then cut it off mid-sentence.
started = time.perf_counter()
speech.stop()
print(f"stop took {time.perf_counter() - started:.3f}s")
speech.wait_until_done()