import logging
import sys
def setup_logging():
    logging.basicConfig(level=logging.INFO,#控制台打印的日志级别
                    #a是追加模式，默认如果不写的话，就是追加模式
                    format=
                    '%(asctime)s - %(pathname)s[line:%(lineno)d] - %(levelname)s: %(message)s',
                    datefmt='%H:%M:%S',
                    #日志格式1
                    force=True,
                    handlers=[
                        logging.FileHandler("em.log"),  # 输出到文件
                        logging.StreamHandler(sys.stdout)  # 输出到控制台
                    ]
                    )
setup_logging()
logger = logging.getLogger()
logger.info("init logging componet successed!")
