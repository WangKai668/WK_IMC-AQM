#!/bin/bash

scenarios=(
    # "Aevaluation0_fat400_a2a_5QP       config-A2A-1-ls400             topology_A2A_fattree          flow_A2A_fattree       threshold"        #.......???.......# 
    "Aevaluation0_simai100_a2a_10QP       config-A2A-1-ls400             topology_simai100          flow_simai_100G       all"    
    # "Aevaluation0_fat400_a2a_10QP2       config-A2A-0-A2A             topology_A2A_fattree          flow_A2A_0_128node_10QP2       all"
    # "Aevaluation0_fat400_a2a_512_node10QP       config-A2A-0-A2A             topology_A2A_0_512node          flow_A2A_0_512node       all"

)

# python3 result_target_dir_original.py -f Aevaluation6_Benchmark-4node/,Aevaluation6_Benchmark-20node/,Aevaluation6_Benchmark-128node/,Aevaluation6_Benchmark-EM/,Aevaluation6_Benchmark-Incast -a 3 --qprange 10000 --stop 10
# python3 result_target_dir_original.py -f Aevaluation5_BasicProperty/ -a 3 --qprange 10000 --stop 10
# python3 result_target_dir_original.py -f Aevaluation2_one400_a2a1Mshort_10QP/ -a 3 --qprange 10000 --stop 10
# python3 result_target_dir_original.py -f Aevaluation1_ls400_a2a1Mshort_10QP/ -a 3 --qprange 10000 --stop 10
# python3 result_target_dir_original.py -f a_point_Test/ -a 3 --qprange 10000 --stop 10



ablation=(0 1 2)

for ((i=0; i<${#scenarios[@]}; i++)); do
    scenario=(${scenarios[$i]})

    output_file=${scenario[0]}
    config_file=${scenario[1]}
    topology_file=${scenario[2]}
    flow_file=${scenario[3]}
    algorithm=${scenario[4]}
    echo "*************** this is ${i}'th scenario *******************"
    echo $output_file, $config_file, $topology_file, $flow_file, $algorithm
    echo ""

    mkdir /mnt/nasDisk/hyj/Sigcomm/${output_file}
    mkdir /mnt/nasDisk/hyj/Sigcomm/${output_file}/mix

    cd /home/r75251/hyj/fullmesh/powertcp_modify/simulator/ns-3.35/examples/All2All

    sed -i "6c TOPOLOGY_FILE examples/All2All/${topology_file}.txt"          ${config_file}.txt
    sed -i "7c FLOW_FILE examples/All2All/${flow_file}.txt"                  ${config_file}.txt
    sed -i "8c TRACE_FILE examples/All2All/trace-equilibrium.txt"             ${config_file}.txt
    sed -i "9c TRACE_OUTPUT_FILE /mnt/nasDisk/hyj/Sigcomm/${output_file}/mix" ${config_file}.txt
    sed -i "10c FCT_OUTPUT_FILE /mnt/nasDisk/hyj/Sigcomm/${output_file}/mix"  ${config_file}.txt
    sed -i "11c PFC_OUTPUT_FILE /mnt/nasDisk/hyj/Sigcomm/${output_file}/mix"  ${config_file}.txt

    if [[ ${config_file} == "config-A2A-8-RealAlexNet" ]];then
        bash script-AlexNet.sh ${algorithm} /mnt/nasDisk/hyj/Sigcomm/${output_file}  /home/r75251/hyj/fullmesh/powertcp_modify/simulator/ns-3.35/examples/All2All/${config_file}.txt &
    elif [[ ${config_file} == "config-A2A-8-MoE" ]];then
        bash script-MoE.sh ${algorithm} /mnt/nasDisk/hyj/Sigcomm/${output_file}  /home/r75251/hyj/fullmesh/powertcp_modify/simulator/ns-3.35/examples/All2All/${config_file}.txt &
    elif [[ ${config_file} == "config-A2A-appendix" ]];then
        bash script-appendix.sh ${algorithm} /mnt/nasDisk/hyj/Sigcomm/${output_file}  /home/r75251/hyj/fullmesh/powertcp_modify/simulator/ns-3.35/examples/All2All/${config_file}.txt &
    elif [[ ${algorithm} == "pabo" ]];then
        wien=true
        for index in ${ablation[@]}; do
            #sed -i "71c ABLATION_STUDY ${index}"     ${config_file}.txt
            #sed -i "73c NIC_Alloc_Factor 0.1"        ${config_file}.txt
            #sed -i "74c Q_SMALL 0"                   ${config_file}.txt

            bash script-equilibrium.sh pabo /mnt/nasDisk/hyj/Sigcomm/${output_file}  /home/r75251/hyj/fullmesh/powertcp_modify/simulator/ns-3.35/examples/All2All/${config_file}.txt ${index} & # & #  ${index} &
            sleep 5
        done
    else
        bash script-equilibrium.sh ${algorithm} /mnt/nasDisk/hyj/Sigcomm/${output_file}  /home/r75251/hyj/fullmesh/powertcp_modify/simulator/ns-3.35/examples/All2All/${config_file}.txt &
    fi


    sleep 60
    echo "##################################"
    echo "#          sleep over            #"
    echo "##################################"

done

