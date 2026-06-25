import sys
import random
import math
import heapq
from optparse import OptionParser
from custom_rand import CustomRand
import os

default_output = "tmp_traffic.txt"
output_prefix = "traffic/"
#基准开始时间
# base_t = 2000000000
base_t = 0

class Flow:
	def __init__(self, src, dst, size, t):
		self.src, self.dst, self.size, self.t = src, dst, size, t
	def __str__(self):
		return "%d %d 3 100 %d %.9f"%(self.src, self.dst, self.size, self.t)

def translate_bandwidth(b):
	if b == None:
		return None
	if type(b)!=str:
		return None
	if b[-1] == 'G':
		return float(b[:-1])*1e9
	if b[-1] == 'M':
		return float(b[:-1])*1e6
	if b[-1] == 'K':
		return float(b[:-1])*1e3
	return float(b)

def poisson(lam):
	return -math.log(1-random.random())*lam

if __name__ == "__main__":
	port = 80
	parser = OptionParser()
	parser.add_option("-c", "--cdf", dest = "cdf_file", help = "the file of the traffic size cdf", default = "uniform_distribution.txt")
	parser.add_option("-n", "--nhost", dest = "nhost", help = "number of hosts")
	parser.add_option("--lmin", "--load-min", dest = "minimum_load", help = "the percentage of the traffic load to the network capacity, by default 0.1", default = "0.1")
	parser.add_option("--lmax", "--load-max", dest = "maximum_load", help = "the percentage of the traffic load to the network capacity, by default 0.9", default = "0.9")
	parser.add_option("--lstep", "--load-step", dest = "load_step", help = "the step of load percentage, by default 0.1", default = "0.1")
	parser.add_option("-b", "--bandwidth", dest = "bandwidth", help = "the bandwidth of host link (G/M/K), by default 10G", default = "10G")
	parser.add_option("-t", "--time", dest = "time", help = "the total run time (s), by default 10", default = "10")
	parser.add_option("-o", "--output", dest = "output", help = "the output file", default = "tmp_traffic.txt")
	parser.add_option("-s", "--scene", dest = "scene", help = "the scene name", default = "LSS")
	
	options,args = parser.parse_args()

	if not options.nhost:
		print ("please use -n to enter number of hosts")
		sys.exit(0)
	nhost = int(options.nhost)
	load_min = float(options.minimum_load)
	load_max = float(options.maximum_load)
	load_step = float(options.load_step)
	bandwidth = translate_bandwidth(options.bandwidth)
	time = float(options.time)*1e9 # translates to ns
	output = options.output
	if bandwidth == None:
		print ("bandwidth format incorrect")
		sys.exit(0)

	fileName = options.cdf_file

	print("cdf file: %s"%(fileName))
	print("nhost: %d, load-min: %f, load-max: %fm, load-step: %f, bandwidth: %f, time: %f"%(nhost, load_min, load_max, load_step, bandwidth, time))

	file = open(fileName,"r")
	lines = file.readlines()

	# for line in lines:#输出文件看看呢
	# 	print(line.strip())


	# read the cdf, save in cdf as [[x_i, cdf_i] ...]
	cdf = []
	for line in lines:
		x,y = map(float, line.strip().split(' '))

		if y<=1:#如果是百分比，则转换成0-100
			y *= 100

		cdf.append([x,y])

	print("cdf read: %s"%(cdf))

	# create a custom random generator, which takes a cdf, and generate number according to the cdf
	customRand = CustomRand()
	if not customRand.setCdf(cdf):
		print ("Error: Not valid cdf")
		sys.exit(0)

	scence_file = output_prefix+options.scene+"/scence.txt"
	#不存在则创建文件夹
	if not os.path.exists(output_prefix+options.scene):
		os.makedirs(output_prefix+options.scene)

	with open(scence_file, "w") as sf:
		# 输出场景信息
		sf.write("cdf file: %s\n"%(fileName))
		sf.write("nhost: %d, load-min: %f, load-max: %f, load-step: %f, bandwidth: %f, time: %f\n"%(nhost, load_min, load_max, load_step, bandwidth, time))

	def frange(start, stop, step, accuracy=1)->list:
		temp_list = []
		temp_list+=[start]
		while start < stop:
			start += step
			start = round(start, 1)
			temp_list.append(start)
		return temp_list

	loads = frange(load_min, load_max, load_step)
	print("loads: %s"%(loads))

	for load in loads:
		# round用于解决浮点数精度问题，frange用于生成浮点数范围的列表
		# 没有frange，自己实现一个

		# #精确到小数点后一位
		load = round(load, 1)
		print("generating traffic for load: %f"%(load))

		# if output == default_output:
		cdf_name = fileName.split('/')[-1].split('.')[0]
		# 前缀/场景/分布类型/负载.txt
		output = output_prefix+options.scene+"/"+cdf_name+"/"+str(load)+".txt"#"traffic_%s_n%d_l%f_b%g_t%ds.txt"%(cdf_name, nhost, load, bandwidth, time/1e9)
		
		if not os.path.exists(output_prefix+options.scene+"/"+cdf_name):
			os.makedirs(output_prefix+options.scene+"/"+cdf_name)

		ofile = open(output, "w")

		# generate flows
		avg = customRand.getAvg()

		print(f"Average flow size: {avg} bytes")

		avg_inter_arrival = 1/(bandwidth*load/8./avg)*1000000000
		n_flow_estimate = int(time / avg_inter_arrival * nhost)

		print(f"n_flow_estimate: {n_flow_estimate}")

		n_flow = 0
		ofile.write("%d \n"%n_flow_estimate)
		host_list = [(base_t + int(poisson(avg_inter_arrival)), i) for i in range(nhost)]
		heapq.heapify(host_list)
		while len(host_list) > 0:
			t,src = host_list[0]
			inter_t = int(poisson(avg_inter_arrival))
			new_tuple = (src, t + inter_t)
			dst = random.randint(0, nhost-1)
			while (dst == src):
				dst = random.randint(0, nhost-1)
			if (t + inter_t > time + base_t):
				heapq.heappop(host_list)
			else:
				size = int(customRand.rand())
				if size <= 0:
					size = 1
				n_flow += 1;
				ofile.write("%d %d 3 100 %d %.9f\n"%(src, dst, size, t * 1e-9))
				heapq.heapreplace(host_list, (t + inter_t, src))
		ofile.seek(0)
		ofile.write("%d"%n_flow)
		ofile.close()

		print("output file: %s, n_flow: %d"%(output, n_flow))

'''
	f_list = []
	avg = customRand.getAvg()
	avg_inter_arrival = 1/(bandwidth*load/8./avg)*1000000000
	# print avg_inter_arrival
	for i in range(nhost):
		t = base_t
		while True:
			inter_t = int(poisson(avg_inter_arrival))
			t += inter_t
			dst = random.randint(0, nhost-1)
			while (dst == i):
				dst = random.randint(0, nhost-1)
			if (t > time + base_t):
				break
			size = int(customRand.rand())
			if size <= 0:
				size = 1
			f_list.append(Flow(i, dst, size, t * 1e-9))

	f_list.sort(key = lambda x: x.t)

	print len(f_list)
	for f in f_list:
		print f
'''