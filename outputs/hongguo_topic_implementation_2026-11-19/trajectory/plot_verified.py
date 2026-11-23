"""Create the figures from the independently checked album-pair sample."""
from pathlib import Path
from statistics import mean, median
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.ticker import FuncFormatter, MaxNLocator
from season_windows import HERE, rows

mac_font = Path('/System/Library/Fonts/Hiragino Sans GB.ttc')
if mac_font.is_file():
    font_manager.fontManager.addfont(str(mac_font))
    font = font_manager.FontProperties(fname=str(mac_font))
else:
    font = font_manager.FontProperties(family=['Noto Sans CJK SC','Source Han Sans SC','sans-serif'])
plt.rcParams.update({'font.family':font.get_name(),'axes.spines.top':False,'axes.spines.right':False,
                     'axes.unicode_minus':False,'axes.labelsize':11,'xtick.labelsize':9,'ytick.labelsize':9,
                     'svg.fonttype':'path','figure.facecolor':'white','axes.facecolor':'white'})
navy='#124c60'; blue='#4c708b'; orange='#c17d3a'; grey='#68737d'
r = rows(HERE/'verified_event_results.csv')
actual=[x for x in r if x['phase']=='observed_event']
ok={x['new_id']:x for x in actual if x['match_status']=='matched'}
ps=[x for x in rows(HERE/'verified_seven_points.csv') if x['phase']=='observed_event']
case=sorted((x for x in actual if x['family']=='持械入宋'),key=lambda a:a['event_date'])[0]
data=sorted((a for a in ps if a['new_id']==case['new_id']),key=lambda a:int(a['relative_day']))
fig,ax=plt.subplots(figsize=(8.7,4.8))
fig.subplots_adjust(left=.12,right=.96,top=.80,bottom=.23)
fig.text(.065,.939,'《持械入宋》第八季的公开收藏轨迹',fontsize=17,weight='bold',color=navy)
fig.text(.066,.862,'第九季在归档四榜首次出现于 '+case['event_date']+'；七个点均为第八季实际记录',fontsize=10,color=grey)
x=[int(a['relative_day']) for a in data];y=[int(a['old_favorites'])/10000 for a in data]
ax.plot(x,y,marker='o',lw=2.4,ms=6,color=navy)
ax.axvline(0,color=orange,lw=1.2,ls='--')
for k,v in zip(x,y): ax.annotate(f'{v:.1f}',(k,v),xytext=(0,7),textcoords='offset points',ha='center',fontsize=9)
ax.set_xticks(x,[(a['observed_day'][5:]+'\n'+('事件日' if int(a['relative_day'])==0 else f"{int(a['relative_day']):+d}天")) for a in data])
ax.set(ylabel='公开收藏（万）',ylim=(min(y)-2,max(y)+2));ax.grid(axis='y',color='#dce3e8',lw=.7);ax.spines['left'].set_color('#aab6bd');ax.spines['bottom'].set_color('#aab6bd')
fig.text(.065,.045,'案例按该系列首个合格季对展示。橙线为榜单首见日。官网记录第九季首可见日为 10 月 17 日。',color=grey,fontsize=8.6)
for ext in ['svg','png']:fig.savefig(HERE/f'verified_case_trajectory.{ext}',dpi=190)
plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(11,5.25),gridspec_kw={'width_ratios':[1.12,1]})
fig.subplots_adjust(left=.09,right=.97,top=.72,bottom=.205,wspace=.39)
fig.text(.05,.93,'前季收藏仍在增长，但增速随同期参照一起放缓',fontsize=18,weight='bold',color=navy)
fig.text(.05,.85,'40 个完成匹配的季对 · 31 个家族 · 17 个事件日；图中数值限于归档榜单跟踪样本',fontsize=10.5,color=grey)
a,b=axes
for key,c,label in [('old_delta_vs_event',navy,'前季'),('control_delta_vs_event',orange,'同期参照')]:
    means=[mean(float(v[key]) for v in ps if v['new_id'] in ok and int(v['relative_day'])==k)/1000 for k in range(-3,4)]
    a.plot(range(-3,4),means,color=c,label=label,marker='o' if key.startswith('old') else 's',ls='-' if key.startswith('old') else '--',lw=2.25)
a.axvline(0,lw=.9,color=grey,ls=':');a.axhline(0,lw=.5,color=grey)
a.set_title('各季对等权的平均轨迹',loc='left',fontsize=12,pad=11)
a.set(ylabel='较事件日的公开收藏差（千）',xlabel='相对后季首次被观察上榜的天数',xticks=range(-3,4));a.legend(loc='upper left',frameon=False,fontsize=9)
vals=sorted(float(v['relative_change'])/1000 for v in ok.values())
b.axhline(0,color=grey,lw=1);b.scatter(range(1,len(vals)+1),vals,s=22,alpha=.85,color=blue)
b.set_title('季对间差异：17 正、1 平、22 负',loc='left',fontsize=12,pad=11)
b.set(ylabel='前后斜率变化减参照（千／天）',xlabel='季对按相对差由低到高排列');b.set_xticks([1,10,20,30,40]);b.yaxis.set_major_locator(MaxNLocator(6))
for ax in axes:
    ax.grid(axis='y',color='#dce3e8',lw=.65);ax.set_axisbelow(True);ax.spines['left'].set_color('#aab6bd');ax.spines['bottom'].set_color('#aab6bd')
fig.text(.05,.055,'斜率分别用事件前与后各自的两个日间隔计算，避开事件当天。参照仅按事前信息选取；共同推广和未观察曝光仍可能解释变化。',color=grey,fontsize=9)
for ext in ['svg','png']:fig.savefig(HERE/f'verified_matched_trajectories.{ext}',dpi=190)
plt.close(fig)
