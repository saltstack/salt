# SSH Tunnel

The ssh-tunnel action will create a reverse tunnel over webrtc to port 22 on the runner.

## Usage

In order to use this action you must have a sdp offer from your local host and a ssh key pair.
Start with creating an sdp offer on your local machine. Provide these values to the ssh-tunnel
action and wait for output from the action with the sdp reply. Provide the reply to the local
rtcforward.py process by pasting it to stdin. If all goes well the local port on your maching
will be forwarded to the ssh port on the runner.

### Getting an sdp offer

To get an sdp offer start rtcforward.py on you local machine with the offer command.
You can also specify which port on the local machine will be used for the tunnel.

``` bash
$ python3 .github/actions/ssh-tunnel/rtcforward.py offer --port 5222
```

rtcforward.py will create an offer an display it to your terminal. (This example offer has been truncated)
After showing the offer the `rtcforward.py` process will wait for a reply.
```
-- offer --
eyJzZHAiOiAidj0wXHJcbm89LSAzOTQ3Mzg4NjUzIDM5NDczODg2NTMgSU4gSVA0IDAuMC4wLjBcclxu
cz0tXHJcbnQ9MCAwXHJcbmE9Z3JvdXA6QlVORExFIDBcclxuYT1tc2lkLXNlbWFudGljOldNUyAqXHJc
bm09YXBwbGljYXRpb24gMzUyNjkgRFRMUy9TQ1RQIDUwMDBcclxuYz1JTiBJUDQgMTkyLjE2OC4wLjIw
IHVkcCAxNjk0NDk4ODE1IDE4NC4xNzkuMjEwLjE1MiAzNTI2OSB0eXAgc3JmbHggcmFkZHIgMTkyLjE2
OC4wLjIwMSBycG9ydCAzNTI2OVxyXG5hPWNhbmRpZGF0ZTozZWFjMzJiZTZkY2RkMTAwZDcwMTFiNWY0
NTo4Qzo2MDoxMTpFQTo3NzpDMTo5RTo1QTo3QzpDQzowRDowODpFQzo2NDowQToxM1xyXG5hPWZpbmdl
cnByaW50OnNoYS01MTIgNjY6MzI6RUQ6MDA6N0I6QjY6NTQ6NzA6MzE6OTA6M0I6Mjg6Q0I6QTk6REU6
MzQ6QjI6NDY6NzE6NUI6MjM6ODA6Nzg6Njg6RDA6QTA6QTg6MjU6QkY6MDQ6ODY6NUY6OTA6QUY6MUQ6
QjA6QzY6ODA6QUY6OTc6QTI6MkM6NDI6QUU6MkI6Q0Q6Mjk6RUQ6MkI6ODc6NTU6ODg6NDY6QTM6ODk6
OEY6ODk6OTE6QTE6QTI6NDM6NTc6M0E6MjZcclxuYT1zZXR1cDphY3RwYXNzXHJcbiIsICJ0eXBlIjog
Im9mZmVyIn0=
-- end offer --
-- Please enter a message from remote party --
```

### Getting an sdp answer

Provide the offer to the ssh-tunnel action. When the action runs, an answer to the offer will be generated.
In the action output you will see that the offer was recieved and the reply in the output.

```
-- Please enter a message from remote party --
-- Message received --
-- reply --
eyJzZHAiOiAidj0wXHJcbm89LSAzOTQ3Mzg3NDcxIDM5NDczODc0NzEgSU4gSVA0IDAuMC4wLjBcclxu
cz0tXHJcbnQ9MCAwXHJcbmE9Z3JvdXA6QlVORExFIDBcclxuYT1tc2lkLXNlbWFudGljOldNUyAqXHJc
bm09YXBwbGljYXRpb24gNTcwMzkgRFRMUy9TQ1RQIDUwMDBcclxuYz1JTiBJUDQgMTkyLjE2OC42NC4x
MFxyXG5hPW1pZDowXHJcbmE9c2N0cG1hcDo1MDAwIHdlYnJ0Yy1kYXRhY2hhbm5lbCA2NTUzNVxyXG5h
MTc6MEI6RTA6OTA6QUM6RjU6RTk6RUI6Q0E6RUE6NTY6REI6NTA6QTk6REY6NTU6MzY6MkM6REI6OUE6
MDc6Mzc6QTM6NDc6NjlcclxuYT1maW5nZXJwcmludDpzaGEtNTEyIDMyOjRDOjk0OkRDOjNFOkU5OkU3
OjNCOjc5OjI4OjZDOjc5OkFEOkVDOjIzOkJDOjRBOjRBOjE5OjlCOjg5OkE3OkE2OjZBOjAwOjJFOkM5
OkE0OjlEOjAwOjM0OjFFOjRDOkVGOjcwOkY5OkNBOjg0OjlEOjcxOjI5OkVCOkIxOkREOkFEOjg5OjUx
OkZFOjhCOjI3OjFDOjFBOkJEOjUxOjQ2OjE4OjBBOjhFOjVBOjI1OjQzOjQzOjZGOkRBXHJcbmE9c2V0
dXA6YWN0aXZlXHJcbiIsICJ0eXBlIjogImFuc3dlciJ9
-- end reply --
```

# Finalizing the tunnel

Paste the sdp reply from the running action into the running `rtcforward.py` process that created the offer.
After receiveing the offer you will see `-- Message received --` and tunnel will be created.

```
-- offer --
eyJzZHAiOiAidj0wXHJcbm89LSAzOTQ3Mzg4NjUzIDM5NDczODg2NTMgSU4gSVA0IDAuMC4wLjBcclxu
cz0tXHJcbnQ9MCAwXHJcbmE9Z3JvdXA6QlVORExFIDBcclxuYT1tc2lkLXNlbWFudGljOldNUyAqXHJc
bm09YXBwbGljYXRpb24gMzUyNjkgRFRMUy9TQ1RQIDUwMDBcclxuYz1JTiBJUDQgMTkyLjE2OC4wLjIw
IHVkcCAxNjk0NDk4ODE1IDE4NC4xNzkuMjEwLjE1MiAzNTI2OSB0eXAgc3JmbHggcmFkZHIgMTkyLjE2
OC4wLjIwMSBycG9ydCAzNTI2OVxyXG5hPWNhbmRpZGF0ZTozZWFjMzJiZTZkY2RkMTAwZDcwMTFiNWY0
NTo4Qzo2MDoxMTpFQTo3NzpDMTo5RTo1QTo3QzpDQzowRDowODpFQzo2NDowQToxM1xyXG5hPWZpbmdl
cnByaW50OnNoYS01MTIgNjY6MzI6RUQ6MDA6N0I6QjY6NTQ6NzA6MzE6OTA6M0I6Mjg6Q0I6QTk6REU6
MzQ6QjI6NDY6NzE6NUI6MjM6ODA6Nzg6Njg6RDA6QTA6QTg6MjU6QkY6MDQ6ODY6NUY6OTA6QUY6MUQ6
QjA6QzY6ODA6QUY6OTc6QTI6MkM6NDI6QUU6MkI6Q0Q6Mjk6RUQ6MkI6ODc6NTU6ODg6NDY6QTM6ODk6
OEY6ODk6OTE6QTE6QTI6NDM6NTc6M0E6MjZcclxuYT1zZXR1cDphY3RwYXNzXHJcbiIsICJ0eXBlIjog
Im9mZmVyIn0=
-- end offer --
-- Please enter a message from remote party --
eyJzZHAiOiAidj0wXHJcbm89LSAzOTQ3Mzg3NDcxIDM5NDczODc0NzEgSU4gSVA0IDAuMC4wLjBcclxu
cz0tXHJcbnQ9MCAwXHJcbmE9Z3JvdXA6QlVORExFIDBcclxuYT1tc2lkLXNlbWFudGljOldNUyAqXHJc
bm09YXBwbGljYXRpb24gNTcwMzkgRFRMUy9TQ1RQIDUwMDBcclxuYz1JTiBJUDQgMTkyLjE2OC42NC4x
MFxyXG5hPW1pZDowXHJcbmE9c2N0cG1hcDo1MDAwIHdlYnJ0Yy1kYXRhY2hhbm5lbCA2NTUzNVxyXG5h
MTc6MEI6RTA6OTA6QUM6RjU6RTk6RUI6Q0E6RUE6NTY6REI6NTA6QTk6REY6NTU6MzY6MkM6REI6OUE6
MDc6Mzc6QTM6NDc6NjlcclxuYT1maW5nZXJwcmludDpzaGEtNTEyIDMyOjRDOjk0OkRDOjNFOkU5OkU3
OjNCOjc5OjI4OjZDOjc5OkFEOkVDOjIzOkJDOjRBOjRBOjE5OjlCOjg5OkE3OkE2OjZBOjAwOjJFOkM5
OkE0OjlEOjAwOjM0OjFFOjRDOkVGOjcwOkY5OkNBOjg0OjlEOjcxOjI5OkVCOkIxOkREOkFEOjg5OjUx
OkZFOjhCOjI3OjFDOjFBOkJEOjUxOjQ2OjE4OjBBOjhFOjVBOjI1OjQzOjQzOjZGOkRBXHJcbmE9c2V0
dXA6YWN0aXZlXHJcbiIsICJ0eXBlIjogImFuc3dlciJ9
-- Message received --
```

SSH to your local port.

```
ssh -o StrictHostKeychecking=no -o TCPKeepAlive=no -o StrictHostKeyChecking=no -vv -p 5222 runner@localhost
```
