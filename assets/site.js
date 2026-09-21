document.querySelectorAll('a[href^="#"]').forEach(a=>{a.addEventListener('click',e=>{const id=a.getAttribute('href');if(id.length>1){const el=document.querySelector(id);if(el){e.preventDefault();el.scrollIntoView({behavior:'smooth'});}}});});

document.querySelectorAll('[data-carousel]').forEach(carousel=>{
  const track=carousel.querySelector('[data-carousel-track]');
  const slides=[...carousel.querySelectorAll('.rm-carousel-slide')];
  const prev=carousel.querySelector('[data-carousel-prev]');
  const next=carousel.querySelector('[data-carousel-next]');
  const dotsWrap=carousel.querySelector('[data-carousel-dots]');
  if(!track||slides.length===0)return;

  const dots=slides.map((_,i)=>{
    const dot=document.createElement('button');
    dot.type='button';
    dot.className='rm-carousel-dot'+(i===0?' active':'');
    dot.tabIndex=-1;
    dotsWrap?.appendChild(dot);
    return dot;
  });

  const nearestIndex=()=>{
    const left=track.scrollLeft;
    let best=0;
    let bestDist=Infinity;
    slides.forEach((slide,i)=>{
      const dist=Math.abs(slide.offsetLeft-left);
      if(dist<bestDist){bestDist=dist;best=i;}
    });
    return best;
  };

  const go=index=>{
    const i=Math.max(0,Math.min(slides.length-1,index));
    slides[i].scrollIntoView({behavior:'smooth',block:'nearest',inline:'start'});
  };

  prev?.addEventListener('click',()=>go(nearestIndex()-1));
  next?.addEventListener('click',()=>go(nearestIndex()+1));

  let raf=0;
  track.addEventListener('scroll',()=>{
    cancelAnimationFrame(raf);
    raf=requestAnimationFrame(()=>{
      const active=nearestIndex();
      dots.forEach((dot,i)=>dot.classList.toggle('active',i===active));
    });
  },{passive:true});

  track.addEventListener('keydown',e=>{
    if(e.key==='ArrowLeft'){e.preventDefault();go(nearestIndex()-1);}
    if(e.key==='ArrowRight'){e.preventDefault();go(nearestIndex()+1);}
  });
});
