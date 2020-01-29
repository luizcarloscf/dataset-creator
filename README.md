# Dataset Creator

This repository contains some utilities to create a multi-camera dataset using Intelligent Space infrastructure for gestures and actions recognition.

## Running on a docker container

The scripts on this projects loads all videos on your memory. So, if you have access to some computer with more RAM memory, you can run everything on a docker container and have access to the graphic interfaces generate by the scripts here.

To do some, accees your remote computer with memory available and leave the container running:

```bash
docker run -d -p 44544:22 -v path/to/your/dataset:/path/to/container/filesystem -e ssh_key="your_public_ssh_key" luizcarloscf/dataset-creator:0.0.1
```

After that, on your computer run:

```bash
ssh -XY -p 44544 root@remoteComputer
```
remenber to update on the file **options.json** the correct path to your dataset.
