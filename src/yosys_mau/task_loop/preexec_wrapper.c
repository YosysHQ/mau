#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <unistd.h>
#include <signal.h>
#include <sys/wait.h>

int main(int argc, char *argv[])
{
    if (argc < 3) {
        fprintf(stderr, "missing arguments\n");
        exit(1);
    }

    if (setpgid(0, 0) < 0) {
        perror("unexpected error setting process group");
        kill(getpid(), SIGKILL);
        exit(1);
    }

    int monitor_pipe_fd = atoi(argv[1]);

    int child_pid = fork();

    if (child_pid < 0) {
        perror("unexpected error forking");
        kill(getpid(), SIGKILL);
        exit(1);
    }

    if (!child_pid) {
        child_pid = fork();

        if (child_pid < 0) {
            perror("unexpected error forking");
            kill(0, SIGKILL);
            exit(1);
        }

        if (!child_pid) {

            close(0);
            close(1);
            close(2);

            char buf[1];
            while (read(monitor_pipe_fd, buf, 1) < 0) {
                if (errno != EINTR) {
                    kill(0, SIGKILL);
                    exit(1);
                }
            }

            sigset_t sigset;
            sigemptyset(&sigset);
            sigaddset(&sigset, SIGHUP);
            sigprocmask(SIG_BLOCK, &sigset, NULL);
            kill(0, SIGHUP);
            kill(0, SIGCONT);
            sigprocmask(SIG_UNBLOCK, &sigset, NULL);
            kill(0, SIGKILL);
            exit(1);
        }

        _exit(0);
    }

    wait(NULL);

    close(monitor_pipe_fd);

    execvp(argv[2], &argv[3]);
    perror("unexpected error in exec");
    kill(0, SIGKILL);
}
