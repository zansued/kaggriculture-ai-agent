"""c17: refreshed 8-cow/5-sheep/6-strawberry common field plan with the strongest locally tested market schedule."""
import base64
import copy
import json
import zlib

_TRACE = json.loads(zlib.decompress(base64.b85decode(
    'c-rk<%Wfn|a{L#b>%e;Or5m@qcBZkMW`oUEVKrzB2G9xugw<iBo1lMJPqQj3Gu_<W+#`w)?c9hWSsCwiw=gsR`G3y-?bqM_{<q)G{^{qlPq&{xpM71N{rj)~`LF-=?SpSW{{7eA{^M`|{q5(U&wl*yu>JPi(GP$6^4DK(KYsY>_U>$P_U?XnwpboM{=D73|MuZe+q?UZXN$|($Gac5w~zaeKX32ujvp=UM{D#~U;lS8Zuy_Se7Jl6%eVGFe)-<Ep$k8s?Y5sEzqj_|{lnvrXJ4nC`n^$~9`4_NdG|PLSE85uf4i8s>eGjJfBEuh^k1W9?OU@L|Mb*Up@A!}UGoOq-M-uIe>-{le7rif;`5K&?I+ZZ!$2JWbJUp6_h0spw#}M-BD89KoV-~p{`~uFO`bfRpw)C7wzvC*BM-<@SgFG!hp`$r=-sWEj^U%HAEf0wd*<QG;PU&nMm|0cTXp*ErvqX9$oQM5Ywp|V-9By~!tafi*z`Pc7y8qn;vpRlg5!Ea?U>Hr&;YQ`!sRu35E*26E`d|gAE0@YXARqr09yCsZ$T5a?}0Q^v#0Kd8?L!wDuy3&D<axs`_X>-{iF^1NkTK?&JkJvhcSbbejL!zPwH8sy!Gr5+ku_^K>9*PZN8_K!JB<ut;=>**#RG>6pr`PPizX!Alefn|0>v^I7T1v<GwKCI<$oha6D+oWibrZyg6|2^zN>Nw-7jz*;Yv{*jZofC-!vKm+D4XmuNYfe)3a45k{$#G>hWHcNh<!!ON0AfJcJISm*xkZu{=>mp^YG9zWcD_?O9&NX7E&);58+7K+`&P)Y51Fa+J6IEpZ%Ck<_C?IeEC>~swy#p$Bkq@vyT5BHx6&l<JZJ`il0<DvSLQsV<xjd_-tqZB-`5M))l=)ORdm2)^5d6#A{ho(NEC)!Spw!hvP5}4)sQkjNQi}!mFCoi_iJcZI0@f>Y}ojE>;Ju>{}W6;$3i)oV+<F7RN_;s`2y^<D}S4`!bhaqSg3p>Wj*TT0#L$C(EZPh<ilS4ugaXDcir$R6{rw!>6K<KGsy*L-@9_z*6M=96?Bc6aLW=~v3;717&pwU$f<S89tFLEC?YHocB9#Y@qT3-k(R*VXdX@eam9k*Pj!ouO1D9C#HWhyK@jtc0_{3;^<4q}kB&AM1m=7;jt*D!z_9&pUL>^Pz)Rl`RRF{L2?Z%5z5efd#cf-@GUHpOPc9P|!=kJ;bb{o+b2DMxpGqqs?k7KC#UyI6$y$+JUr%YWc7ZkUZRQz8J;pC#6tH|*kTSEx^l{?bd;i3h<8hz22W>s*&WxbD#*!;geJg^Ny5;)%jVdLQ)WqD2bHRc<CJ!otGE3{`<3)^VFj7|24UXAc9zAu7gvUA|X~`Lt82UnnTTUVlW09q_*;iql>c5^Rb|y1;?^KxE@azsqO3>MacF=|fA(Cp&on$%dpy+(@V4bok+qw-5gu{oDzWLq}Jf!%RW?HRdG?OhvDA1GlO~(6IrG&&xr8>hSdAM?>S>vH1M>aJ&1{_Tk~LmOiR;6;Y;eXzJ(*&OJN$L$|#J5+m9JHmc1nQpOP*f756oY(IO{s&HlSu-W;(d7l!UBScB^So;YWiQJgl<<9w{l!_b1-W0e78BrL$GMa$<eX00ZdO}+#*!^;!PLLqq5|BXjDhA)HHlW)5s9XAy>zd1x%|_CPFIqY%=qtEgkAyp~fhO5U-E+F2dVQjx+P=`AF{HK<s1l-H8<}A*JI!QDt=2I*o`-YQ976H>r91YyM`c#P+Y93kG2Z~Y06~XQP?fv+FLj7#4!-oOQ+JN*4+!Ntb!b>(J_?u0IYFokV(4r)3fiEtaAYEu(}<U;K^!u-VV)FnU@Npw1CIufpIuq7hi5tnf_HL#1^Op)L{<boYvYc3U}-N#=JS7lUq-1#mHT7JKv@40f$vo-5(@>Y654nw8Bh~2nMoO{fn^ZXf){3M<OJZkM4&5(Yl(t*9CjelJbikfcL3=A&NPV%{xSg%0Ib3wz2Sa>90UBiUI*paE8T~i`;ZVA;EVA0Fl8(Rnp$Ux^jHTu0oT*xMU+O9iC-!CW`>60ciR2^9ebr^b`i)!T!hSyL;%`=Clf9Li1<(Bwm`WevxcQ|4CcC%Q5hwp^92ic5|YW$vapbYPbH{A{}~NhcTy62xEHhL&Td^x)x`G!Pqu`X<dZc5Mqh>3x`oDYvLJomrn}pZ?|Ve-49Y9<gCn)t`0{t-xpdi?J@1RZi;%ZI0vFAM7S~UT<tsgNgqTZ`1ml}i2%iTHN2xMzOEqX=2wE^M#ot%lj;ON&$PXax)%~+t@XVMrZ0*$Y6Xk|}LD>Z}@<{zfsQGJIoKpCxDqOUqJiMCO<72vvvV{nMD%?vXM@5fKZ)&kALlRgLlONQKT@%{bTY(i_8p;ZXho&9FVzkarsin89S+fCvLE=ud_;LyDLP>~%VmBQc<%e!#^RotXPI^}dRx<<nd(N8HF0^*c5A;q-_nllO^uM_VineTeL(Q~bKSSFylMNcU2z6V}n0(f=&<59KIn7&j$WtM$v`I^v8AmbM9A00Qt0+1DJcunm-2G+05Ko?wLUu2{>QQ<|aN9An$3+c_`K?J9d6Xfrtz2Kc{(=*9g@qdh;QZku#$ubH4P?<RGZcm7<cMUi0xE(2ux%wKI}4g*Xnl-FM>zKC{kp^!C2{=ZQrCqoX51yV=s<!byrQE?(yxeT<Ty{&a9o}&b%IOwXnxF9F?v4Wsa!ygW!F{AUIjQwy3q`T01Fy4irNy{;4h~-S|*^0;N8dgn`S4>7syIVl!CFANTqgdhp+D=i@}~!-o^}?YKIxT05tdsqj|@V=G>1CZ4INksKNa3Fqvx9a=N1J4kQ8QB4Sry&||i`-TP3by&{%NhmhXZ&V`aynh$(Pv_LhCu);y5I1M~Sw<KRSbLydiwIxU!%LpI#li8t^n@tdFM0>Y0?G-(Qq8rSjO#r!sOAUxZbfUX1uR1{oc1^Wi|8+zGoNyQxa;YZ$<1333qZ%Uu5+x464-J$BzRdvkZ8z}CZZHm~Hhb*dwEe?ruJeOw<L!w$dBj6*o&4=o?FLj{mLco>4_mV<m($ziZ@eCHkp2F{4-O(#<zU3v2B_Fq18|lRECr^@c?*TzVs$49I`!jZA!ayb4(#T0H?&lY*(>~Yu)+fq5>T-q3QhA4U+dIGG%zTkDLtamAGXJI(7#Vb=aJ@dz75N!Ez(g*&48qGsi(0$s639M8%*i=od>>gYKAt?4OO#5Q$s2IEaZZ>a=h9ojbLe_%U{p7kLX~~jIY(ol+vlBxI%`l<*$pP3nL|%*;WrH4S`7m)o(jjhET)Mp;WN(kAVhO7#E!Fl;}eb7FY`>H~$P2LCcF`AuQq6YQt&Q_%|5{nhq)_H8Lebn_-cnjR^22&9h8&*6}JS2hbgH(A7q<sq#nI&#NZ7M;kb@dXwM?y`6p)=*aj(mQt4{?Yuv)C1m8J70o&YrV&=iEIbg{L>+^)BvPHWzZDJyNroRH0?Uq*c}|X=Yz5kbr2Wu|A^9m-Dl5v4eWVZ3rv%&{WdK7GS%~=tRgPrHZUuL8hAR>IG>R*QoT{IBqwY$I_nzGw(}cE3&<@%Q%t-Of^WZvh)M>C0h#$euzy_%3U*@?~F|nipZn!yQ7_Uu&Re%F|!i0WeyqMy(EK7koWdSf9lS#%<<|X4mZ1yUvVr*||`B1ZDb6k{$+;GO2)nHJqyObTbD6M@$?yG4|p3`&*?hl&ObixQU$>HQ0$Eeza^gN!&<t3>crF%Q@O)S)Y9se-yvJXVrd4dvkO`w|geW2I^VwUP$!S&Z9cO!b;Ge0(F-^uiHqLyj4*gWy`I%OXNE_jfufV9@K7JcXlTQ!qb4qtTTj1NH=Rxb$GtltP+ld(5`NoWRq(f9SdYVYmMGl4Wk)(Q^?rJqhuU_m}jGZ}f>cP_dQ-ya6h#H3Z><5NjOaOc)nQwRnl?eGmlZ6IWz+F5rXzI2%ygF)!7Db({p5I3~X4!?E{WDP`_G@s(ixYOHk5LpZ#S$7n6fn#w($~a18*$gk^W`xxEf^n2(AqM4VGvNrh*(JB-%z4t`V-!kpqiqwQR@9E%o<bR<l4X<jh-N$lXORd%Jl?w%s3>B+v*MhL!U42&te#Xa(9ps!BIA$KR_N{H(F9Ya0<jH9P3}WxWtwsU^>gh?M3C5V{LW2eIl59i0ND{kDL2|IF*viS-Aq`MSR~=>rL{%Ou!Pnm)k-jE=pt>kNP}sj^Rbrm+7&Wa*R@hB(xh0aD;})^Fv`WnYpcDjOzTA-K!z7$$Fc6o=`;EbGE1eO6|P9Ot%%pWFmXn2vRz+7)JJpsENN=I^)8z&N%ZnmnvtjKAv3WjxhZ;(5QJs;L}5M2HF-0gTBZ!eabmy*n5wCQbH*`Wn6!U&u4@2n&p`AZAux9CT3AD|_xk20;l4!~J<%o#9dF`1m}<kWbwqRDkBmtI7<0SdNZt%NGHT#yJAj(20U}g{!MFjgyoSxn#brf8076GQ*piuvUQP{M7BW4CdpjG!$?kg3yc&+HDafWA7M7I@B(56ln&KzvVS|nh(x3Wu8LJ7x<RTPl9<f(OAYfTNes;6|U<?3ZIUcHRsAY~hW1)4MaV53M<vka3$2eg!N92BGb7#{84h0k!nIxVv8dg?&xEg=<c>mMw<Grmsz!T71HR^^*O!j(Q#JJuWXX=0#b9pxHGChL7YE{H@bLg!~<q$Q5QS-`1bNDoF1R}mjS*4P-hu|<$M0Sgdq%#X$Ep4u@FfId2PQ~=(r%ybURBO4cn%pep!7W2nL9<%R96lpLmF>yR8$_s1JX<XQRmte4fKNH5#*GA(P&N(1UG2tLF9Qg!{Rjq?$R{Y(Mxy`J5t_uZ0E5TII(M`**A-nSU>tDI&#uQAI|2+3Nj>5jvd9cUFaXK{VjR2rr!U>g9Z43CL2a0KD}g;zN*4c~O7CP(QG&lvjuyLnrdV0kZHCuY+6qNY*$m{piB={{SSO4YL{kL~0z~Ffer|AR?4n1>d(;ot4u`BF*5!t60Pf5s1ytb3&EQXJvRdE1R0RlrnRtauNI{>%(IHTGFg>&H2~IpY)kN$h$QDpUv-T-M1!$4fAV=<^=rl{xVbl@bdCAr!gDS$MeuKo&MUf{>XK;YAhBd6tU)YyT2CT7rYz~1%J(10Q6DD(hRiiPmap4ZZbshX6n=|-{`16qe6zN?Jlg+uK1a_m^IPzu;=MqN}o4yRIa{={=hm)7);Hib%s(FR3LPN8ahj)2ToYO&H>khC`0)MCgVdgCq+SZ<W1`FOzaH(diVs%x~VKA?tBH+eGx|(iRMluQ=r3^Vj^8znh0D$@o8YkoAJ@9LmxH>KGXW9R{)kb=ht*XY-s}jo#Oif_vc+`9~t<9OI+}hv@$mVwCRElh`7flpJc0Eg)EqhL#%(NN>MmkT7<uLRm%O><ve`iLJBt2{xeg|&Y?Xkn1#YON)Q62&47yShOjOvLL5hSBHe7`ck0=uu#ScLy%;V#|8%ez%c*Lj1aWBn$J0~>;jj|3kPZBBCyqv%<TeCNcY<V+O7(5*`-*6;r8d1<AJ6vr9<92Jy^Y0Nw;o=F+wEygG)fDsv&kXF}BLW1c!TUnkeq6rf5nN@Z1L$T~|4YwN`d(aV0g68jG(ma6YGb3neB$-N>faJwi?tD)#0LdVwTMV?)_gkW^c4Q<UC2jt-17g3W#yn(Wi85nm_A+JiJegMK&mr_nV-K&FMg@j7-Mb<*28_b`F{^k{k8~G%6t55ZTi{r|B#Kn1!Of&5IVu&ifSgsK>CjVFFAAjH<d!-GBiTASj(UY&r0-N2X(bhJ`%bFRS=5PHlxoEyd2AodmS$+3#Zqhv`7tgW^%|-GIt>)1Xe|KuB^A08sa$09B$km<`&%y!AYKB3Az_{JG{ANXfYXR(Cmg+s<~UPJCh2w)zZW7bp$pYSF;OS7Rn3@Qf;cR)oUul7{pEOT<-4IoUS6td2kgYa*$qG3ZT(H>vte=y*YGs39GheQ#<(GY*k}*@=w>zvL^xpLWlRhaD+O4CMHTN|?9@&Ox0#}NBkdSK;siFvDmUH?hU89D;Lm2ts2MVpTju<3Ai&fmYr`2Nlf!dj*0WsLQ(zh8+GfE&umJ?RuEgj|%yPb@yRGtRK5?lyra0cI5u0pDwO&BLD;C5p<HRysw(0p5ayDsv5om{x0JnG26Yw{I?a(YwHF7!`B`AsI=<Gdv38;8!iV}!$W#IUnaxlcMF)yd<fcs)j+miq~toA(ddfFBIyNWmu)78nkHK#ORQ>lnj@mZ$~d#Q#1yWQ8b^^3S40CP(;Sgp=g;V6)hMy$@Rls6+L2}SSxWr}*E<^-%xmVlk~;jU?pG*M+f)^43CLQ@E;GITuA8I8`o!%id;<+b3sZCUEfNmTh`Ldqbq_N$+Z<?00JV7bZIh93YS&C{yD22sF{1P7Qw4AiNIvbZ!1UU%b8oP4xYs%Ug2o|LoksUkVBtf+2u$nJO<nIxgD6<yXvXfnXas?LTMily<mD&-XQF-HVOShjiY&G)eXf^y);G5>WFvXd5mwSWK@#d2F!^WRg#I;}oOV41cdH*uNO<%=OVVNv@@AyE1a2Gq2eh>{IGi`YwY+YVPTQY`4k$vsMPaov~wK`Ebh(n$hwqqo{BQx|3F^?6_bhgxthr$SR@hJwbMg5P7#>P1P7g@Qcdvy`|c)_5Vb2a-06QS+!CQMjWl89*7|DjrzUn|~S`PWK03fK{3gnfj>q)Hcq+y{1YA870rKK<S2&NEukAQLtjABy0hTOJ8U@&7~e!u>+CaA4?)9o~H<x_C%J&tn<w(8|V$_J%T4}uJ}>OtxusK5Y*l{0%KTGO4r%iG!A5#K%J>^xUdM4b6h54<8?8kpbmgG=`uw?VkxY4TsEAaEbR+!HJBRg@-AmqW2D?jupr`_x!i@6T@~yd4^(<ubvwxsuEr=jKq*XLCprV^#dIkl%gEA>nB>q%ul9hr0f&iDjrtWVmAzFI)1(l`M7=+izxMhMh1aVDkY11l^yWA}VNR?RcMId->#wgx<^^~%1Z5FArjy#%&(9iy$aR8lpcGQGPBa%^yON7ELYGGB2n#Y@JcHZ|3IyP7IY6Fd*Qd?bCSs6uzwJ<ga<3F*60iC`O*~Dnx(GUo!W0&yW;9g^(;SIh1U=!H)0l(Ty19^eLHF%zAMQ0lljzUG?TILoApxPa;*l%ELtm8)zf~zHK2`+(|8PI8&LgC1-@O*>ig2D_e|YkOe(Nn`$;gTTbT>`jY8F-w<{AGwP!-XfG`c>LOHpd%G)-!sbi>0NOuHe9L2Rvrn0FdAwm4zUPLBnEAad?#%xt)H?yQz7P{=5Gyn=(Bo5{7fP+Uv{23Vm-t$+$OQI>#>CNPsggPh<)#;{dgO-B%{PPYzRcrOv6YrH6|WMIXd&;xflVr4YmH<xvy6agZ*EeQdt0B#W7sJs+<MG9)m<dm0YKUL7HLS3_L$F5Jsb?WX#lox^sAoqL&ExTHpCshaZsMG_f%}EX0nK2QuuCz0cOoMY*Q51;M{h0%eL&B5gIjX}^&v9~1$RvfXLvU&b(Zawih!>3Gk#)KbK;dtamz^ISYm-RqV(D37@jM!?u+>{SF5JmIFPW{Y40@a!J98K;op>70ThI+wCX8BcN$iCD1x6dqD6AF;rznz$ZDZI~(J5UCS!!4%V4d^z)(oxqYWDOmTIUU$$&?e~P77#bVliPbx2kBBYRARhnC+4`*sMAd2t(?wm)a|kfTJAb3s6H!!?0Vi0V5Re5F)@TI6bt?dOXxO`mrZoUP`)3y~w;K$@FaaM6E7GI%$)$)@uoB5aKz~wu>VwDMp_L^qQmndL38VMx~-&oYrxI)_BcdX3B@sL8Y^hA?clpnRWF{dcQO%wDw|>)vJ~L;nptRoE}hfR{Vb`{u8y)Te+@JR->A1uLXXDztw9S<05&v`~QiE!!$~>hUp?FOju=arNU*BR(8e`=m-%4@QJ~PIN4Xc%`-t>G}=lfyi!59)~a~pd0Mv++W;+v(wulO%(K9dRYW#loU4o3IICet_fMZHcC6v{haqAv+=eN=fpc--b2ahRWH2G2ycJQV(k9CIowG9-{1HCNJS=E_I8h+%Cg5?=9ul%zAi4}f)aZ0%_CVo80qx#Z0$qtI#1RtD;M%ACnj@bO0u0_ej_H=Ou*BGSj+*N2_C=X;r8(-$C6gMRcgH59Uh+UgHt9_2&QQ9rM_094nw%G$EPF7k87OQ|MW#+jT-u5WdaGM|Gib+w$3bQ?Q`89;j--XD)qPnssE;DwG%w37|3_b7&G4pbJ|DqX3CHy`el-DDHqU59ZXfKuPz%tAQPuacEob8DI>&3?(#2b$eF=2y*9vlR)>jJE0)u4!O#{512i{6Sx8kj%<cx4aTXT`h#-dnOqb|LLPeEUszC%FFL~U0~h<(zRS6U$)0r7GP)FY?Bc$4~v_@gmQCRCHw%XD1SWF`SAjTLF!CCu2qdsI{igP_13)7jctsCfE|_5ywEo<q!tBFh{lhg*YFD0<j|%f^U7s-e}nqqW(Gn@weRK+pkfV@70jvv2p(U#5u>x!)#p-5+L$ac@$}_H3zkt=w2Jv;lYMV44%+`I4?Vu!N@h8(#X-y#;Nycng7Nfcm$4T)?dlE-3hMNwpO{VwXqjRcG-=m050Z`2RJk`UR^riRu#zoIOk~_QNzb|BHrBMDBBRuy?+mlS%xXd(VX1UPxD@G5#>(#bzHYsL$2AnGP7!o3XXJc(t}xvkTEuHNUGOY%~I3DPiPv1@Cm&@}$^OFc1QuB)F$5uu^vXsD)mOO;+aqRrmg4T!NP>pvTZJA}7>K>L~^EO2`t#k(_oh!}yFlQ=qcQ5Thv0l<=>Rs*`8*g`y+d@}g9N3&iP+*#RV9NMo5~Al_Ibo|NMk2yUG9h&-aaB`SD^Y03GaN2H#M_9B%?N4Bq;_%-4fX-oE^4}~f?%srqXoTfY`+z0IvJghP<Q55P>j1E_ugaI4Z*or)tc;p4K?gsgDB}C&|63Q6mG>dlZczk+86$NJ79xfse9*F$syOch#?Z=gx?Tdt(YB4ej&r!8zL#!)tK>+N4+NVJY-zXu5yZLaKVCx(CONz9qf@|TwKqOMzR>7=A8`IcgZ@@w3n!dbNjg^tuZB_V&(#8zvG}pjULpLu_$@GKU9k2?MeR{E6Wfly@+ymjUU+c!U+tOuI+_&~>gHMBV?V8(>0wAwZgSaV54F$lU7XwQk$J5cUKpazW+_L|2qW(UM2(ij^(pfMXs+8&~x|Whsy3~3Xd3QY)s|A9XSkB^JT7^Vz?UblZSE?}={(DrpW(res6$3ff;e2gMW=70>OP(9Xi{LrzzU`M~`)yXAQ-V$K{a=KaI3y-VM!&9?kP{XfHE0S_bc!3rH!Ew9#cu-UimizZkkHVwdu=(~mzlcb)X$fu8k89!QZ)_@){C)`h?f)d9Db-w+6tt@Tp`g?Y%bJ-aS&~r!iR+3taFa?i>UC0W0p))+8rhJv1FbS9&)$xhb~?ktbdKSdD&f%Z9Zl%2qrizV=9p#Zkkp!j1KHnl|mD`KLn;ErCm(_G=X;pz#E`U(*<tPL5@$WxQ^F(@ZMVLw<3%J52$h>K`ySqKyODXAwR7|m@qQduMz0l)-Q5a8CNOv6NQn2X=rM>KycIg;=Q=z0uvD*RjI+~0mOqhT*I9Sy}6-WI1ZVMGEmJ(M{0I}M+Qa|sPLu$PZB!$N<ZD2SbnP;6uvL=u4z3yZ#x5-%hyf`obXUD>_l8w27L7*3e(_!dV8v!p9;?8)i5I-oT>^s0cNR7@l#~I7eXu<bQy}oLcbHmlYYMiuhf!7y8AT_P?S2V5k`{G!B)Wzu=1FBNJLs>IA68~TN$|oi%lu*C{l-H&~lT-CPBRmMq*)vJ@8c;J$VSayrWvd0`(HF#WEUdbk~s9C|VayC5wK7PS+|uO~00a<1CjLq!@@C3$*dNB;6FJhRcE^)s{*3gp-8y0g-6OD_yvJI&GQTx|GqD9Z|OSicjz>5$7+2BCGn1592IqRhM`P##notFi)g)C&*+F!K3CQGAAWz7+)1}07s%&x1h`oE`yc{-gW@bqEKV1pN?P)3vzR@XBk*kZ-u}Nnezeiz5-CWT(lv3oyCfNGhct{UA@%qTl1cI)O0@}P0(7LuBJ7-ch&4UFP*A9<%`ZX*vu<s`y|e7#%$giNOl^(wYO%jCi!o?y^5NQMjR5~=<D<(equUEM~$zYbH2C4QvkdK1d@0|5vp5<>X*Z}A70*++<^lAB<!A$%q&b<@`S93yzl|w6%M;faj^x|ouXw-yJ>%bk?xLrK}RzV(N)r^o0hm=maP*PxD*~MPFvMO4bIGN?v0cz%@QErePox>1UQaX%=v|jj3f|vv~R-G;E5uo?5ObmeLqjCe>Oq}a&pZZa5BgxW%N4==IX5i9dKo*4CJqxijT77Eh4(m3ztf{GOc|g8XQ@xQRyQb@a+#j%*xvBX@nJ-9WXQyMW-wdBRq;dm1P6=_`>JGl=;5mY9er_Q<o@+?b_-l#<qx*%|q|F3;In_j2D%gRi(GG1kn<B;$f#~QbaK#Ww)U&d%vm@&C|z_GMz0yR-|qP!67Fd<(QBn4b6g86xp7a0Z8P4*Dk6=P=J;ny!K3W-z+h`;;Ow}RLYFxLW=APtcSh&*oRC$|Nh=QhTrFjGE8BKa`kl9bPntWD^*FHzJx%qZRTPEuHW5$JiY|wTdKXZT_0@w9Q#S+#!9**>H8FvoYsno5}>H)VDw)s;S6tMnNtxx<M@R>z|2bKs{z|y_W$OK*M8!^AyRe+tnwjS$w(}2{+t^<1hu;gbvTJC6{X=(9!sNm3j?T;;_AF)%O+AXgB!2xG9!PVjL+NyGlkWGjX;%^uANJ<zJvnjOe3w-3!?N|rS0WQ0Kjr!?36wXQM|uM=H=vF*WdGmNg*K(umed2A>4zvR?Lu{<Lq~6*@Ynv`ag@9P9x1_t+pQBA90b!+$M>07G|x-6691fDD3P0W5_vmuK$B+VldXM0vuU3biIKA^RK~bF9+~_qzW*Mv$UY4(n|L3XGe`(!(7|sinp5%i!-VZgUprcDN?D!b><3_Gn#bMoq#4co3SnfJ>7)%y-SlCdfm*q=KrY3&L#mCkel&XPvgRTmlYSZJc>h*5sBMN;E;(t=p512bPrNyN@eji4hCrmR&LvN9e6-+7wOW~JM7>VN~*#}|EfCF<ZZ84wwHt_j?6)KekT`Wq60jRZbcPIgLf{;k7AQ1n#kJtLn*E>6>m`njgJ4-lvF{Yr;1I5o-9I>&I9USxRABRX$j^TKO9K3)4-Y!Gzp?OG$<W!-{uunB6|xHw`tEO%`*d%sirJw#w&;*4g&uxu6rqViBTEO>-&S8ZhU2XXI~KhHx+tWC+0?=N_a5n)I=oMSx|LSR8(I$^LQ<s3G6C|1}m&{ZsHmO@z+jQ)(J4)*(7?EQsQInpOJ!qD~@=bri0S~Xnv>$)%j*esHx`=(Wpy~T?_5_AZOX8R4Y|4xtH}L^j<#dh17M;1Zr3nZElJ_xRhVz>^5_Tf|^aXBf7lIN9-kd5r=-3$fGpX^}hG#$+q?nct}tF34A1;9HzRH=g2&a%H*rA6O8;k(I-DL8V%ZMJ9|5^1Crm}iFtX=*dS9a3Y~wscu&W89o@Dbl<ID#p}nEDIP_>=H+Y0Br;02~DvW)d7+xNugs)QJnxK<<d>0jsPS9tRV(RRYXmyjQ13@;eT85iKqUIFJ6!cmr>|NsEmZ7=+KHe$foQXyADr2KX^(Bf2E4^i}LCt7tx0+`Q;}V7UgA^F^<~Qlr;(bkgZr#)qVCFC;YQi*1XH2JCI~K4rZ{-%ymA07O(#}6BvbY4=p;pt6r~3KRD>9moq?3##5!;dUD5|FTgwxo@-G1p)b|c)d+78IUJ=&Hk{eDNKw*}+4s9uP8J<m+a%vi3{b#Ii54(>3QA)tg1b*8rohdGGU@_kG8Cizve#>Yk#P_bEI2X=I$D3JyQO#}63dkHAT<|mC#0(!Nu^gCzim8-gm`xzByt!&py33xaB%v_BJYJQFE6J^7A!r3xlLaLmnUn~ttHCp&%qP4Bc*y?wB{4Q*#IxYx#QnvDM!WAI^-=aBT;JH=-M%91eR?DSN5~8b>ExWPK6~D%f(VaQ?_hgnnD>A;#hcPnILwDx!Oq#hWQg;)I(O$t$yB0iaE{^=25NP)$VS6T*Rwx)OtY<GXnLd-qv{}+AReKZuiVHMx&5Y^lzW&;$OX)K2z#v1=wX83($IrB%Yqc<eW=_$yx6Cgg+#dU(g3YCC37C=&9|5!A;UlTF`<K%>N6%(Xpz|x)rw0W+15KUP5>jul6D5c?fUmxaKHJaW1vA<47wzHQzEBJ9UaBiz8)s?ca^uV>4Tk{;+xqG5_T6?^ahpA@`1?nrAv-=3{JGGL#J|Z0Fb>v84@Vri*=JX<v9SL_AIHy0b#e~@UA6Sm)NVigVhR<LhNnAhADQX3X_s0LJ06l;(^qo8qaR|uPSp5mfb{kM0CG?phX'
)).decode("utf-8"))

_SELLABLE = ("STRAWBERRY", "MELON", "MILK", "WOOL", "EGG", "TOMATO", "CARROT", "WHEAT", "FERTILIZER")

_FRONT_RUN_HORIZON = 1
_FRONT_RUN_ITEMS = ("MELON", "STRAWBERRY", "MILK", "WOOL")
_BASE_PRICE = {"MELON": 250, "STRAWBERRY": 120, "MILK": 160, "WOOL": 200}
_GLUT_WEIGHT = {"MELON": 3.5, "STRAWBERRY": 2.0, "MILK": 2.0, "WOOL": 3.2}
_LAST_STEP = -1
_CLONE_CONFIDENCE = 0


def _public_signature(farm):
    """Compact public fingerprint for detecting a mirrored build."""
    counts = {item: 0 for item in (
        "COW", "SHEEP", "GOOSE", "WHEAT", "CARROT", "TOMATO",
        "STRAWBERRY", "MELON", "PASTURE", "COOP", "WEED",
    )}
    for row in farm.get("tiles", []) or []:
        for tile in row or []:
            if not isinstance(tile, dict):
                continue
            for key in ("animal", "crop", "kind"):
                value = tile.get(key)
                if value in counts:
                    counts[value] += 1
                    break
    positions = [farm.get("farmer", [0, 0]), *(farm.get("hands", []) or [])]
    return (
        len(farm.get("hands", []) or []),
        tuple(sorted(farm.get("unlocked_quadrants", []) or [])),
        tuple(sorted(tuple(position) for position in positions)),
        tuple(counts[item] for item in sorted(counts)),
    )


def _signature_distance(left, right):
    distance = abs(left[0] - right[0])
    distance += 3 * abs(len(left[1]) - len(right[1]))
    distance += sum(abs(a - b) for a, b in zip(left[3], right[3]))
    if left[2] != right[2]:
        distance += 2
    return distance


def _update_clone_profile(obs, step):
    global _CLONE_CONFIDENCE
    if step not in (4, 24) and not (step >= 48 and step % 24 == 0):
        return
    farms = obs.get("farms", []) or []
    if len(farms) < 2:
        return
    player = int(obs.get("player", 0) or 0)
    distance = _signature_distance(
        _public_signature(farms[player]),
        _public_signature(farms[1 - player]),
    )
    if distance <= 1:
        _CLONE_CONFIDENCE = min(8, _CLONE_CONFIDENCE + 1)
    elif distance <= 4:
        _CLONE_CONFIDENCE = max(0, _CLONE_CONFIDENCE - 1)
    else:
        _CLONE_CONFIDENCE = max(0, _CLONE_CONFIDENCE - 3)


def _front_run(action, obs, step):
    """Sell one premium line immediately before a clone's expected glut."""
    if _CLONE_CONFIDENCE < 2 or _FRONT_RUN_HORIZON <= 0:
        return
    orders = list(action.get("market", []) or [])
    if len(orders) >= 10:
        return
    already = {}
    for order in orders:
        if isinstance(order, list) and len(order) >= 3 and order[0] == "SELL":
            already[order[1]] = already.get(order[1], 0) + max(0, int(order[2] or 0))
    planned = {}
    end = min(len(_TRACE), step + _FRONT_RUN_HORIZON + 1)
    for future_step in range(step + 1, end):
        distance = future_step - step
        for order in _TRACE[future_step].get("market", []) or []:
            if not (
                isinstance(order, list) and len(order) >= 3
                and order[0] == "SELL" and order[1] in _FRONT_RUN_ITEMS
            ):
                continue
            item = order[1]
            quantity = max(0, int(order[2] or 0))
            if item not in planned:
                planned[item] = [distance, quantity]
            else:
                planned[item][1] += quantity
    shed = (obs.get("private") or {}).get("shed") or {}
    prices = ((obs.get("market") or {}).get("prices") or {})
    choices = []
    for item, (distance, quantity) in planned.items():
        available = max(0, int(shed.get(item, 0) or 0) - already.get(item, 0))
        quantity = min(available, quantity)
        if quantity <= 0:
            continue
        price = float(prices.get(item, _BASE_PRICE[item]) or 0)
        priority = (
            price * quantity * _GLUT_WEIGHT[item]
            + (_FRONT_RUN_HORIZON + 1 - distance) * _BASE_PRICE[item]
        )
        choices.append((priority, item, quantity))
    if choices:
        _, item, quantity = max(choices)
        orders.append(["SELL", item, quantity])
        action["market"] = orders[:10]


def _terminal_liquidation(action, obs, step):
    """Replay-derived safety net: leave no sellable shed inventory at season end."""
    if step < 680:
        return
    shed = (obs.get("private") or {}).get("shed") or {}
    market = action.setdefault("market", [])
    already = {
        order[1]
        for order in market
        if isinstance(order, list) and len(order) >= 2 and order[0] == "SELL"
    }
    for item in _SELLABLE:
        qty = int(shed.get(item, 0) or 0)
        if qty > 0 and item not in already and len(market) < 10:
            market.append(["SELL", item, qty])


def _shed_access(size):
    half = size // 2
    return [(half - 1, half - 1), (half, half - 1), (half - 1, half), (half, half)]


def _move_toward(pos, target, tiles):
    x, y = pos
    tx, ty = target
    choices = []
    if tx < x:
        choices.append(("WEST", (x - 1, y)))
    if tx > x:
        choices.append(("EAST", (x + 1, y)))
    if ty < y:
        choices.append(("NORTH", (x, y - 1)))
    if ty > y:
        choices.append(("SOUTH", (x, y + 1)))
    size = len(tiles)
    for op, (nx, ny) in choices:
        if 0 <= nx < size and 0 <= ny < size and tiles[ny][nx] != "LOCKED":
            return [op]
    return ["PASS"]


def _terminal_action(obs):
    """Observation-driven final-eight-turn harvest/drop/sell controller."""
    player = int(obs.get("player", 0) or 0)
    farm = (obs.get("farms") or [])[player]
    private = obs.get("private") or {}
    tiles = farm.get("tiles") or []
    size = len(tiles)
    positions = [farm.get("farmer", [0, 0]), *(farm.get("hands") or [])]
    inventories = list(private.get("inventories") or [])
    inventories.extend({} for _ in range(len(positions) - len(inventories)))
    sheds = set(_shed_access(size))

    available = {
        (x, y)
        for y, row in enumerate(tiles)
        for x, tile in enumerate(row)
        if isinstance(tile, dict) and int(tile.get("yield_units", 0) or 0) > 0
    }
    actions = []
    pending = {}
    for pos_raw, inventory in zip(positions, inventories):
        pos = tuple(pos_raw)
        inventory = inventory or {}
        load = sum(max(0, int(v or 0)) for v in inventory.values())
        x, y = pos
        tile = tiles[y][x] if 0 <= y < size and 0 <= x < size else None
        if load > 0 and pos in sheds:
            action = ["DROP"]
            for item, count in inventory.items():
                if item in _SELLABLE:
                    pending[item] = pending.get(item, 0) + max(0, int(count or 0))
        elif isinstance(tile, dict) and int(tile.get("yield_units", 0) or 0) > 0:
            action = ["HARVEST"]
            available.discard(pos)
        elif load > 0:
            target = min(sheds, key=lambda q: abs(q[0] - x) + abs(q[1] - y))
            action = _move_toward(pos, target, tiles)
        elif available:
            target = min(available, key=lambda q: (abs(q[0] - x) + abs(q[1] - y), q[1], q[0]))
            available.discard(target)
            action = _move_toward(pos, target, tiles)
        elif isinstance(tile, dict) and tile.get("fertilizer_available", False):
            action = ["COLLECT_FERTILIZER"]
        else:
            action = ["PASS"]
        actions.append(action)

    shed = dict(private.get("shed") or {})
    for item, count in pending.items():
        shed[item] = int(shed.get(item, 0) or 0) + count
    prices = ((obs.get("market") or {}).get("prices") or {})
    sells = [
        (int(shed.get(item, 0) or 0) * int(prices.get(item, 1) or 1), item, int(shed.get(item, 0) or 0))
        for item in _SELLABLE
    ]
    sells = [row for row in sells if row[2] > 0]
    sells.sort(reverse=True)
    market = [["SELL", item, qty] for _, item, qty in sells[:10]]
    if int(obs.get("hour", 0) or 0) <= 1:
        already = int(farm.get("hires_today", 0) or 0)
        for _ in range(min(10 - len(market), max(0, 8 - already))):
            market.append(["HIRE"])
    return {"farmer": actions[0], "hands": actions[1:], "market": market[:10]}


def agent(obs, config=None):
    global _LAST_STEP, _CLONE_CONFIDENCE
    step = min(int(obs.get("step", 0) or 0), len(_TRACE) - 1)
    if step == 0 or step <= _LAST_STEP:
        _CLONE_CONFIDENCE = 0
    _LAST_STEP = step
    _update_clone_profile(obs, step)
    if step >= 717:
        return _terminal_action(obs)
    action = copy.deepcopy(_TRACE[step])
    _front_run(action, obs, step)
    _terminal_liquidation(action, obs, step)
    return action
