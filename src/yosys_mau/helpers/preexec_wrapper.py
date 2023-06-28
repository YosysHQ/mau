import os
import signal
import sys

if __name__ == "__main__":  # pragma: no cover
    # exiting via SIGHUP or os.execl breaks coverage collection, so we ignore this for coverage

    # First move to a new process group with this process as leader. If a subprocess explicitly
    # changes the process group without reliably handling process cleanup there is little we can do
    # about it.
    #
    # Since this pattern ties the lifetime of this new process group to the lifetime of the parent
    # process which remains in its original process group, there is no issue with using this
    # recursively. I.e. while we do change the process group, we make sure that the new process
    # group cannot outlive the parent process.
    os.setpgid(0, 0)

    # The parent process gives us a read end of a pipe and keeps the write end open. When the parent
    # exits (that includes crashing) that read end sees an EOF. The parent can also explicitly
    # close the write end to trigger a process cleanup.
    parent_monitor_fd = int(sys.argv[1])

    # We use a separate process to monitor this pipe. We use a double fork to reduce the risk of the
    # process we are execing below messing with our monitor process.
    if not os.fork():
        if not os.fork():
            parent_monitor = os.getpid()

            # Don't keep stdio open
            os.close(0)
            os.close(1)
            os.close(2)

            # When the parent crashed or wants us to clean up, we get an eof on this pipe, until
            # then this will block.
            os.read(parent_monitor_fd, 1)

            # To cleanup deliver SIGHUP/SIGCONT combo to the whole process group, temporarily
            # masking the SIGHUP so we get a chance to deliver the SIGCONT before our default SIGHUP
            # handler terminates us.

            # The SIGHUP/SIGCONT combo is also delivered by the operating system when a process
            # group becomes orphaned due to an exiting process, so this is a well established
            # pattern to clean up a process group.
            signal.pthread_sigmask(signal.SIG_BLOCK, [signal.SIGHUP])
            os.kill(0, signal.SIGHUP)
            os.kill(0, signal.SIGCONT)
            signal.pthread_sigmask(signal.SIG_UNBLOCK, [signal.SIGHUP])

            # This should never be reached

        sys.exit(0)

    os.wait()  # wait for the child to exit

    try:
        os.execl(sys.argv[2], *sys.argv[3:])
    except OSError:
        # This should only happen when there's a race condition between our parent resolving the
        # path and us trying to execute it. While it's too late to generate a synchronous exception,
        # using kill makes sure that whatever return code convention the invoked process uses, the
        # parent can tell that this was not a normal exit.
        os.kill(0, signal.SIGKILL)
        pass
