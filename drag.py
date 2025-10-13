import sys
import win32api
import win32con
import win32gui

# Window procedure
def wndproc(hwnd, msg, wparam, lparam):
    if msg == win32con.WM_DROPFILES:
        hDrop = wparam
        try:
            # number of files dropped
            count = win32api.DragQueryFile(hDrop, -1)
            if count > 0:
                filepath = win32api.DragQueryFile(hDrop, 0)
                print(filepath)
                sys.stdout.flush()
        finally:
            win32api.DragFinish(hDrop)
        win32gui.PostQuitMessage(0)
        return 0

    if msg == win32con.WM_DESTROY:
        win32gui.PostQuitMessage(0)
        return 0

    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)



def main():
    hInstance = win32api.GetModuleHandle(None)
    className = "SimpleDropWindow"

    wc = win32gui.WNDCLASS()
    wc.style = win32con.CS_VREDRAW | win32con.CS_HREDRAW
    wc.lpfnWndProc = wndproc
    wc.hInstance = hInstance
    wc.hCursor = win32gui.LoadCursor(None, win32con.IDC_ARROW)
    wc.hbrBackground = win32con.COLOR_WINDOW + 1
    wc.lpszClassName = className

    try:
        atom = win32gui.RegisterClass(wc)
    except Exception:
        # might already be registered; that's fine
        atom = win32gui.GetClassInfo(hInstance, className)

    # Create a small, centered window with instructions
    width, height = 420, 120
    screen_x = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
    screen_y = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
    left = int((screen_x - width) / 2)
    top = int((screen_y - height) / 2)

    hwnd = win32gui.CreateWindowEx(
        0,
        className,
        "Drop .lua / .zip file",
        win32con.WS_OVERLAPPED | win32con.WS_SYSMENU | win32con.WS_CAPTION,
        left, top, width, height,
        None, None, hInstance, None
    )

    # Allow drag-and-drop of files onto this window
    win32gui.DragAcceptFiles(hwnd, True)

    # Create a simple static text inside the window
    win32gui.CreateWindowEx(
        0, "STATIC",
        "Drag a .lua or .zip file here.",
        win32con.WS_CHILD | win32con.WS_VISIBLE | win32con.SS_CENTER,
        10, 10, width - 20, height - 20,
        hwnd, 0, hInstance, None
    )

    win32gui.ShowWindow(hwnd, win32con.SW_SHOWNORMAL)
    win32gui.UpdateWindow(hwnd)

    # Run message loop (blocks until WM_QUIT posted)
    while True:
        bRet, msg = win32gui.GetMessage(None, 0, 0)
        if bRet == 0:
            break  # WM_QUIT
        elif bRet == -1:
            break  # Error
        win32gui.TranslateMessage(msg)
        win32gui.DispatchMessage(msg)

if __name__ == "__main__":

    # Friendly reminder: run from a console so prints are visible.
    print("Window created. Drop a file onto it to print the path and exit.")
    main()
