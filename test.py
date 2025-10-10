from multiprocessing import Process
import time
import sys

def worker():
    try:
        while True:
            print("Working...")
            time.sleep(1)
    except KeyboardInterrupt:
        # In case you stop it manually
        print("Worker stopped")

if __name__ == "__main__":
    p = Process(target=worker)
    p.start()
    print("Press Enter to stop the worker.")
    
    input()  # wait for user to press Enter
    print("Stopping...")
    
    p.terminate()  # send SIGTERM (kill)
    p.join()       # wait for it to finish cleanup
    
    print("Process terminated.")
    sys.exit(0)
