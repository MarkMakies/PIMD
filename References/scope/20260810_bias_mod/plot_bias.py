import csv, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, NullFormatter
from matplotlib.lines import Line2D

D   = "/home/mark/Projects/PIMD/References/scope/20260810_bias_mod"
OUT = "/home/mark/Projects/PIMD/References/images/bias_mod_null_20260810.png"
SURF="#fcfcfb"; INK="#0b0b0b"; INK2="#52514e"; GRID="#e7ebef"
COL={"air":"#2a78d6","brass":"#eb6834","steel":"#1baf7a"}   # documented slots 1-3
FILE={"air":"air","brass":"brass","steel":"steel_rhs"}
BANDS=[("100us","100 µs @ 3.125 kHz"),("50us","50 µs @ 5 kHz"),("10us","10 µs @ 25 kHz")]
CLIP=1.35   # V — above this the capture window saturates

import json
PROF=json.load(open("/home/mark/Projects/PIMD/src/data/profiles/cal_3x10_v2.json"))
CELLS={f"{int(b['pulse_us'])}us":b["delays_us"] for b in PROF["bands"]}

def load(band,k):
    """Decay only: everything after the last saturated sample."""
    sd,v=[],[]
    for r in csv.DictReader(open(f"{D}/{band}_{FILE[k]}.csv")):
        sd.append(float(r["sample_delay_us"])); v.append(float(r["ch1_V"]))
    last=max((i for i,x in enumerate(v) if x>=CLIP), default=-1)
    out=[(s,x*1000) for s,x in list(zip(sd,v))[last+1:] if s>0 and x>0]
    return [p[0] for p in out],[p[1] for p in out]

fig,axes=plt.subplots(1,3,figsize=(13.2,4.9),dpi=200)
fig.patch.set_facecolor(SURF)
fig.subplots_adjust(left=0.055,right=0.988,top=0.70,bottom=0.135,wspace=0.20)

for ax,(band,title) in zip(axes,BANDS):
    ax.set_facecolor(SURF)
    a_sd,a_v=load(band,"air")
    w=[(s,x) for s,x in zip(a_sd,a_v) if 11<=s<=26]; nb,nv=min(w,key=lambda p:p[1])
    aq=sum(x for s,x in zip(a_sd,a_v) if s>=max(a_sd)-1.0)/max(1,len([s for s in a_sd if s>=max(a_sd)-1.0]))
    x0=min(a_sd); x1=max(a_sd); ends=[]
    for k in ("air","brass","steel"):
        sd,v=load(band,k)
        ax.plot(sd,v,lw=1.9,color=COL[k],solid_capstyle="round",zorder=3)
        ends.append([v[-1],k])
    ax.axhline(aq,color="#8a97a3",lw=0.9,ls=(0,(4,3)),zorder=2)
    ax.plot([nb],[nv],marker="o",ms=7,mfc=SURF,mec=COL["air"],mew=2.0,zorder=6)
    ax.annotate(f"air bottoms {nv:.0f} mV\nat sd {nb:.2f} µs",xy=(nb,nv),
                xytext=(nb*1.06,nv*0.72),fontsize=8.3,color=INK2,
                arrowprops=dict(arrowstyle="-",color="#8a97a3",lw=0.8))
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlim(x0*0.97,x1*1.30); ax.set_ylim(45,1600)
    for i,c in enumerate(CELLS[band]):
        if x0*0.97<=c<=x1*1.30:
            ax.axvline(c,color="#b9c2cc",lw=0.7,ls="-",alpha=0.55,zorder=1)
            ax.plot([c],[47.5],marker="^",ms=4.5,color="#6b7885",clip_on=False,zorder=7)
    xt=[t for t in (10,12,15,20,25,30,40) if x0*0.97<=t<=x1*1.30]
    ax.xaxis.set_major_locator(FixedLocator(xt))
    ax.set_xticklabels([str(t) for t in xt],fontsize=8.6)
    yt=[50,100,200,500,1000]
    ax.yaxis.set_major_locator(FixedLocator(yt))
    ax.set_yticklabels([str(t) for t in yt],fontsize=8.6)
    ax.xaxis.set_minor_formatter(NullFormatter()); ax.yaxis.set_minor_formatter(NullFormatter())
    ax.tick_params(which="minor",length=0)
    ends.sort(key=lambda e:-e[0])
    for j in range(1,len(ends)):
        if ends[j-1][0]/ends[j][0] < 1.15: ends[j][0]=ends[j-1][0]/1.15
    for ey,k in ends:
        ax.annotate(k,xy=(x1,ey),xytext=(5,0),textcoords="offset points",
                    fontsize=8.6,color=INK2,va="center",zorder=5)
    ax.text(x0*0.99,aq*1.06,f"{aq:.0f} mV quiescent",fontsize=7.9,color=INK2,va="bottom")
    ax.set_title(title,fontsize=10.5,color=INK,fontweight="bold",loc="left",pad=8)
    ax.grid(which="major",color=GRID,lw=0.8,zorder=0)
    ax.grid(which="minor",color=GRID,lw=0.5,alpha=0.6,zorder=0)
    for s in ("top","right"): ax.spines[s].set_visible(False)
    for s in ("bottom","left"): ax.spines[s].set_color("#b9c2cc")
    ax.tick_params(colors=INK2,length=3)
    ax.set_xlabel("sample delay after coil turn-off  (µs, log)",fontsize=9.0,color=INK2)
axes[0].set_ylabel("mV at the amplifier input  (log)",fontsize=9.2,color=INK2)

fig.text(0.055,0.955,"Measured at the LT6203 input with the +97 mV bias fitted — 64 averages, "
         "targets at 0 cm, 2026-08-10. Sample delay from the MCLK edge on CH2.",
         fontsize=9.2,color=INK)
fig.text(0.055,0.917,"The bias puts the whole transient above zero, so air's negative lobe can be "
         "shown on a log axis at all. Grey verticals and ▲ marks are the current cal_3x10_v2 cells; "
         "traces start where the capture window stops saturating.",
         fontsize=8.8,color=INK2)
fig.text(0.055,0.845,"The null, and what a target does to it",fontsize=15.5,
         fontweight="bold",color=INK)
fig.legend(handles=[Line2D([],[],color=COL[k],lw=2.4,label=l) for k,l in
                    (("air","air (baseline)"),("brass","brass block — non-ferrous"),
                     ("steel","RHS steel tube — ferrous"))],
           loc="upper right",bbox_to_anchor=(0.988,0.885),frameon=False,fontsize=9,ncols=3,
           handletextpad=0.5,columnspacing=1.6,labelcolor=INK2)
fig.savefig(OUT,facecolor=SURF,bbox_inches="tight")
print("wrote",OUT)
