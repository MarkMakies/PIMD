import csv, json, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, NullFormatter
from matplotlib.lines import Line2D

D="/home/mark/Projects/PIMD/References/scope/20260810_bias_mod"
OUT="/home/mark/Projects/PIMD/References/images/bias_mod_delay_plot_20260810.png"
FITS=json.load(open("/home/mark/.claude/jobs/74b03c28/tmp/fits_final.json"))
PROF=json.load(open("/home/mark/Projects/PIMD/src/data/profiles/cal_3x10_v3.json"))
CELLS={f"{int(b['pulse_us'])}us":b["delays_us"] for b in PROF["bands"]}
SURF="#fcfcfb"; INK="#0b0b0b"; INK2="#52514e"; GRID="#e7ebef"
COL={"air":"#2a78d6","brass":"#eb6834","steel":"#1baf7a"}
FILE={"air":"air","brass":"brass","steel":"steel_rhs"}
BANDS=[("100us","100 µs @ 3.125 kHz"),("50us","50 µs @ 5 kHz"),("10us","10 µs @ 25 kHz")]
CLIP=1.35

def load(band,k):
    sd,v=[],[]
    for r in csv.DictReader(open(f"{D}/{band}_{FILE[k]}.csv")):
        sd.append(float(r["sample_delay_us"])); v.append(float(r["ch1_V"]))
    last=max((i for i,x in enumerate(v) if x>=CLIP), default=-1)
    a=np.array([(s,x*1000) for s,x in list(zip(sd,v))[last+1:] if s>0 and x>0])
    return a[:,0],a[:,1]
def curve(d,t):
    p=d["p"]
    if d["kind"]=="repeated":
        Q,R,tau,Vq=p; return (Q+R*t)*np.exp(-t/tau)+Vq
    A,tf,C,ts,Vq=p; return A*np.exp(-t/tf)+C*np.exp(-t/ts)+Vq

fig,axes=plt.subplots(1,3,figsize=(13.2,5.1),dpi=200); fig.patch.set_facecolor(SURF)
fig.subplots_adjust(left=0.055,right=0.988,top=0.685,bottom=0.13,wspace=0.20)

for ax,(band,title) in zip(axes,BANDS):
    ax.set_facecolor(SURF); ends=[]; tmin=1e9; tmax=0; lines=[]
    for k in ("air","brass","steel"):
        t,v=load(band,k); tmin=min(tmin,t.min()); tmax=max(tmax,t.max())
        ax.plot(t,v,lw=1.9,color=COL[k],solid_capstyle="round",zorder=3)
        d=FITS[f"{band}|{k}"]
        ax.plot(t,curve(d,t),lw=1.5,ls=(0,(1.6,1.8)),color=COL[k],alpha=0.95,zorder=4)
        ends.append([v[-1],k])
        lines.append(f"{k}  τ={d['tau']:.2f} µs" if d["kind"]=="repeated"
                     else f"{k}  τf={d['tau_fast']:.2f}  τs={d['tau_slow']:.1f} µs")
        lines[-1]+=f"   ±{d['rms']:.1f} mV"
    for c in CELLS[band]:
        if tmin*0.85<=c<=tmax*1.35:
            ax.axvline(c,color="#b9c2cc",lw=0.7,alpha=0.55,zorder=1)
            ax.plot([c],[47.5],marker="^",ms=4.5,color="#6b7885",clip_on=False,zorder=7)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlim(tmin*0.93,tmax*1.35); ax.set_ylim(45,1600)
    xt=[x for x in (7,8,10,12,15,20,25,30,40,50) if tmin*0.93<=x<=tmax*1.35]
    ax.xaxis.set_major_locator(FixedLocator(xt)); ax.set_xticklabels([str(x) for x in xt],fontsize=8.6)
    yt=[50,100,200,500,1000]
    ax.yaxis.set_major_locator(FixedLocator(yt)); ax.set_yticklabels([str(y) for y in yt],fontsize=8.6)
    ax.xaxis.set_minor_formatter(NullFormatter()); ax.yaxis.set_minor_formatter(NullFormatter())
    ax.tick_params(which="minor",length=0)
    ends.sort(key=lambda e:-e[0])
    for j in range(1,len(ends)):
        if ends[j-1][0]/ends[j][0]<1.15: ends[j][0]=ends[j-1][0]/1.15
    for ey,k in ends:
        ax.annotate(k,xy=(tmax,ey),xytext=(5,0),textcoords="offset points",
                    fontsize=8.6,color=INK2,va="center",zorder=5)
    ax.text(0.975,0.965,"\n".join(lines),transform=ax.transAxes,ha="right",va="top",
            fontsize=8.0,color=INK2,linespacing=1.5,family="DejaVu Sans",
            bbox=dict(boxstyle="round,pad=0.45",fc=SURF,ec="#dfe4ea",lw=0.8))
    ax.set_title(title,fontsize=10.5,color=INK,fontweight="bold",loc="left",pad=8)
    ax.grid(which="major",color=GRID,lw=0.8,zorder=0)
    ax.grid(which="minor",color=GRID,lw=0.5,alpha=0.6,zorder=0)
    for s in ("top","right"): ax.spines[s].set_visible(False)
    for s in ("bottom","left"): ax.spines[s].set_color("#b9c2cc")
    ax.tick_params(colors=INK2,length=3)
    ax.set_xlabel("sample delay after coil turn-off  (µs, log)",fontsize=9.0,color=INK2)
axes[0].set_ylabel("mV at the amplifier input  (log)",fontsize=9.2,color=INK2)

fig.text(0.055,0.960,"Measured at the LT6203 input with the +97 mV bias fitted — 64 averages, "
         "targets at 0 cm, 2026-08-10. Sample delay from the MCLK edge on CH2.",fontsize=9.2,color=INK)
fig.text(0.055,0.925,"Dotted = fitted model, solid = measurement. Air and brass need only a single "
         "(repeated) pole; steel needs a second, slow one — that slow τ is the target's own eddy decay.",
         fontsize=8.8,color=INK2)
fig.text(0.055,0.893,"Grey verticals and ▲ are the cal_3x10_v3 cells. Traces start where the capture "
         "window stops saturating, so the first cells of each band are off the left of the data.",
         fontsize=8.8,color=INK2)
fig.text(0.055,0.815,"cal_3x10_v3 — the delay plot",fontsize=15.5,fontweight="bold",color=INK)
fig.legend(handles=[Line2D([],[],color=COL[k],lw=2.4,label=l) for k,l in
                    (("air","air (baseline)"),("brass","brass block — non-ferrous"),
                     ("steel","RHS steel tube — ferrous"))],
           loc="upper right",bbox_to_anchor=(0.988,0.862),frameon=False,fontsize=9,ncols=3,
           handletextpad=0.5,columnspacing=1.6,labelcolor=INK2)
fig.savefig(OUT,facecolor=SURF,bbox_inches="tight"); print("wrote",OUT)
