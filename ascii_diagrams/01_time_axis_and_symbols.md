# 01 时间轴和符号

## MATRIX 的基本时间尺度

MATRIX 当前实验按 2 FPS 使用：

```text
frame:  f0     f1     f2     f3     f4     f5
time:   0ms    500ms  1000ms 1500ms 2000ms 2500ms
        |------|------|------|------|------|
```

所以：

```text
fixed_1  = 1 帧延迟  = 500ms
fixed_2  = 2 帧延迟  = 1000ms
fixed_3  = 3 帧延迟  = 1500ms
fixed_5  = 5 帧延迟  = 2500ms
fixed_10 = 10 帧延迟 = 5000ms
```

## 一条 support 消息的生命周期

```text
frame:       f10    f11    f12    f13
time:        |------|------|------|

support:     S(cap)
                    \
                     \
                      S(arr)

含义：
S 在 f10 被 support UAV 捕获；
如果 delay = 2 帧，它到 f12 才到达主 UAV。
```

## 在线发布约束

```text
frame:       f10    f11    f12
             |------|------|
output:      pub    pub    pub
support:     S(cap) -----> S(arr)

f10 的结果在 f10 已经发布。
f11 的结果在 f11 已经发布。
S 到 f12 才到达，所以它不能改变已经发布出去的 f10/f11 在线结果。
```

这就是为什么“消息最终到达”和“消息对在线跟踪有帮助”不是同一件事。

## 三个常见时间

```text
capture time:  观测发生在哪里
arrival time:  主 UAV 什么时候收到
publish time:  在线系统什么时候必须输出结果
```

当前实验最核心的冲突是：

```text
support 的信息属于 capture time
但在线系统只能在 arrival time 之后使用它
而 publish time 不等人
```
