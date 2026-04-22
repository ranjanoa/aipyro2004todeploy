import eventlet
# CRITICAL: Monkey patch must happen before ANY other imports to green threading.RLock
eventlet.monkey_patch(all=True)
import dns
# Force dns to use eventlet's socket if it was already loaded
try:
    import eventlet.support.dnspython
    eventlet.support.dnspython.patch_dnspython()
except:
    pass
print("[INIT] AGGRESSIVE Eventlet Monkey Patch applied")
