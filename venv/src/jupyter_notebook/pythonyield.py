def consumer():
    result = ''
    print("consumer method run")
    while True:
        print('[CONSUMER] 挂起')
        next = yield result
        print('[CONSUMER] 恢复--并接受到数据%s' % next)
        result = '200 OK'

def produce(coroutine):
    print('[PRODUCER] 准备启动协程')
    next(coroutine)
    sendData = 0
    while sendData < 2:
        sendData = sendData + 1
        print('[PRODUCER] 发送数据 %s' % sendData)
        result1 = coroutine.send(sendData)
        print('[PRODUCER] 处理结果: %s' % result1)
    coroutine.close()

coroutine = consumer()
produce(coroutine)