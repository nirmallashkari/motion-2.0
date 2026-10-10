"""Local visual selection for passages outside automatic subject coverage."""

ACTION_NAMES = {
    "Object close-up": "cutaway", "Travel along a route": "travel",
    "Move between places": "transfer", "Pair two views": "pair",
    "Compare two views": "compare", "Build a sequence": "build",
    "Orbit around a subject": "orbit",
}


def choose_visuals(missing, store, smoke_test=False):
    import tkinter as tk
    from tkinter import ttk, messagebox
    from PIL import Image, ImageTk

    window = tk.Tk()
    window.title("Motion 2.0 - Choose a visual")
    window.geometry("1040x730")
    window.minsize(900, 680)
    outer = ttk.Frame(window,padding=20)
    outer.pack(fill="both",expand=True)
    ttk.Label(outer,text="Choose an object for this passage",font=("Segoe UI",19,"bold")).pack(anchor="w")
    ttk.Label(outer,text="This passage needs a visual choice. Your original script and voice will stay unchanged.").pack(anchor="w",pady=(8,14))
    cue_label = ttk.Label(outer,text="",wraplength=950,font=("Segoe UI",13))
    cue_label.pack(anchor="w",pady=(0,20))
    body = ttk.Frame(outer)
    body.pack(fill="both",expand=True)
    left = ttk.Frame(body)
    left.pack(side="left",fill="both",expand=True)
    ttk.Label(left,text="Search an English object name, such as book, train, mountain, or coin.").pack(anchor="w")
    query = tk.StringVar()
    entry = ttk.Entry(left,textvariable=query,font=("Segoe UI",12))
    entry.pack(fill="x",pady=10)
    listing = tk.Listbox(left,exportselection=False,font=("Segoe UI",11),height=18)
    listing.pack(fill="both",expand=True)
    right = ttk.Frame(body,padding=(25,0,0,0))
    right.pack(side="right",fill="y")
    preview = ttk.Label(right)
    preview.pack(pady=25)
    name_label = ttk.Label(right,text="Select an object",font=("Segoe UI",13,"bold"))
    name_label.pack()
    ttk.Label(right,text="Animation preset").pack(pady=(25,8))
    action = tk.StringVar(value="Object close-up")
    ttk.Combobox(right,textvariable=action,values=list(ACTION_NAMES),state="readonly",width=29).pack()
    results = {}
    state = {"index":0,"name":None,"photo":None}
    all_names = store.names()

    def update_list(*args):
        term = query.get().strip().casefold().replace(" ","-")
        listing.delete(0,"end")
        names = [name for name in all_names if term in name]
        for name in names[:500]:
            listing.insert("end",name)
        state["name"] = None
        name_label.config(text=f"{len(names)} matching objects")

    def selected(event=None):
        indexes = listing.curselection()
        if not indexes:
            return
        name = listing.get(indexes[0])
        try:
            path,_ = store.icon(name,"teal")
            with Image.open(path) as image:
                picture = Image.new("RGBA",(290,290),"#0c1428")
                resized = image.convert("RGBA").resize((260,260),Image.Resampling.LANCZOS)
                picture.alpha_composite(resized,(15,15))
                photo = ImageTk.PhotoImage(picture)
            state.update(name=name,photo=photo)
            preview.config(image=photo)
            name_label.config(text=name)
        except Exception as exc:
            messagebox.showerror("Asset error",str(exc),parent=window)

    def next_passage():
        cue = missing[state["index"]]
        cue_label.config(text=f"Passage {state['index']+1}/{len(missing)}  |  Cue {cue['cue_id']}\n\n{cue['text']}")
        query.set("")
        action.set("Object close-up")
        entry.focus_set()

    def accept():
        if not state["name"]:
            messagebox.showinfo("Choose an object","Select an object from the list first.",parent=window)
            return
        cue = missing[state["index"]]
        results[str(cue["cue_id"])] = dict(icon=state["name"],action=ACTION_NAMES[action.get()])
        state["index"] += 1
        if state["index"] == len(missing):
            window.destroy()
        else:
            next_passage()

    def cancel():
        results.clear()
        window.destroy()

    buttons = ttk.Frame(outer)
    buttons.pack(fill="x",pady=(20,0))
    ttk.Button(buttons,text="Cancel",command=cancel).pack(side="left")
    ttk.Button(buttons,text="Use visual and continue",command=accept).pack(side="right")
    query.trace_add("write",update_list)
    listing.bind("<<ListboxSelect>>",selected)
    listing.bind("<Double-Button-1>",lambda event:accept())
    window.protocol("WM_DELETE_WINDOW",cancel)
    next_passage()
    if smoke_test:
        window.withdraw()
        window.after(300,cancel)
    window.mainloop()
    return results
