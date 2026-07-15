# Server Environment Check Commands

用于判断实验室服务器是否适合搭建 MATRIX 异步多无人机 BEV / 世界坐标实验环境，以及是否适合 MLMF / ROS / Gazebo 相关平台验证。

## PyTorch / CUDA

```bash
python3 -c 'import torch; print("torch:", torch.__version__); print("torch cuda:", torch.version.cuda); print("cuda available:", torch.cuda.is_available()); print("device count:", torch.cuda.device_count()); [print(i, torch.cuda.get_device_name(i)) for i in range(torch.cuda.device_count())]'
```

不要复制终端里显示的 `>`。如果使用 `python3 - <<'PY'` 这种多行写法，`>` 只是 shell 等待继续输入时显示的提示符，不是命令内容；结束标记 `PY` 还必须单独一行并且顶格。

## GPU Driver / Runtime

```bash
nvidia-smi
```

## OS Version

```bash
lsb_release -a
```

## Disk Space

```bash
df -h
```

## Memory

```bash
free -h
```

## Optional: ROS / Gazebo

如果后续要搭建 MLMF / ROS / Gazebo 环境，再运行下面命令：

```bash
echo "$ROS_DISTRO"
rosversion -d
gazebo --version
```
