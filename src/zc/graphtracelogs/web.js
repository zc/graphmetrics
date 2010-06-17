dojo.require("dijit.form.Button");
dojo.require("dijit.Menu");
dojo.require("dijit.form.DateTextBox");
dojo.require("dijit.form.CheckBox");
dojo.require("dijit.form.TextBox");
dojo.require("dijit.form.FilteringSelect");
dojo.require("dojo.data.ItemFileReadStore");

zc = function() {
    // var data = [{x: 1, y: 1}, {x: 2, y: 2}];

    // var update = function(value) {
    //     data[0] = {x: 1, y: 2};
    //     data[1] = {x: 2, y: 1};
    //     zc.chart1.updateSeries('Series 1', data);
    //     zc.chart1.render();
    // };
    var imgid = 0;
    var customers;

    var newInstanceMenuButton = function(label, instfunc) {
        var customer_menu = new dijit.Menu({ style: "display: none;" });
        for (var ic=0; ic < customers.length; ic++) {
            var hosts = customers[ic][1];
            var host_menu = new dijit.Menu({ style: "display: none;" });
            for (var ih=0; ih < hosts.length; ih++) {
                var instances = hosts[ih][1];
                var instance_menu = new dijit.Menu({ style: "display: none;" });
                for (var ii=0; ii < instances.length; ii++) {
                    instance_menu.addChild(new dijit.MenuItem({
                        label: instances[ii][0],
                        onClick: dojo.partial(instfunc, instances[ii][1])
                    }));
                }
                host_menu.addChild(new dijit.PopupMenuItem({
                    label: hosts[ih][0],
                    popup: instance_menu
                }));
            }
            customer_menu.addChild(new dijit.PopupMenuItem({
                label: customers[ic][0],
                popup: host_menu
            }));
        }
        return new dijit.form.ComboButton({
            label: label,
            dropDown: customer_menu
        })
    };

    var newChart = function(inst) {
        imgid ++;
        var div = dojo.create('div',{}, dojo.body())
        var params = {
            instance: inst,
            bust: 0
        };
        var img = dojo.create(
            'img', {id: 'img'+imgid,
                    src: 'show.png?'+dojo.objectToQuery(params)}, div);
        var update_img = function (ob) {
            if (ob != undefined)
                dojo.mixin(params, ob);
            params.bust++;
            img.src =  'show.png?'+dojo.objectToQuery(params);
        };
        var keep_refreshing = function () {
            if (params.end == null)
                update_img();
            setTimeout(keep_refreshing, 60000);
        };
        setTimeout(keep_refreshing, 60000);
        dojo.create('br', {}, div);
        div.appendChild(new dijit.form.Button({
            label: 'Reload',
            onClick: update_img
        }).domNode);
        div.appendChild(new dijit.form.DateTextBox({
            onChange: function(date) {
                if (date != null)
                    date = (date.getFullYear()+'-'+(date.getMonth()+1)
                            +'-'+date.getDate());
                update_img({start: date});
            }
        }).domNode);
        dojo.style(div.lastChild, "width", "10em");
        dojo.place('<span> to </span>', div)
        div.appendChild(new dijit.form.DateTextBox({
            onChange: function(date) {
                if (date != null)
                    date = (date.getFullYear()+'-'+(date.getMonth()+1)
                            +'-'+date.getDate());
                update_img({end: date});
            }
        }).domNode);
        dojo.style(div.lastChild, "width", "10em");
        dojo.place('<span> Trail: </span>', div)
        div.appendChild(new dijit.form.ValidationTextBox({
            maxLength: 3,
            regExp: "[0-9]+",
            onChange: function(val) {
                update_img({trail: val});
            }
        }).domNode);
        dojo.style(div.lastChild, "width", "4em");
        dojo.place('<span> Log: </span>', div)
        div.appendChild(new dijit.form.CheckBox({
            onChange: function(val) {
                if (val)
                    params.log = 'y';
                else
                    params.log = 'n';
                update_img();
            }
        }).domNode);
        div.appendChild(newInstanceMenuButton(
            "Instance:",
            function(val){ update_img({instance: val}); }
        ).domNode);
    };

    var replaceAll = function(str, orig, repl) {
        while (1) {
            var news = str.replace(orig, repl)
            if (news == str) return str;
            str = news;
        }
    };

    return {
        init: function()
        {
            dojo.xhrGet({
                url: 'get_instances.json',
                handleAs: 'json',
                load: function (data) {
                    customers = data.customers;
                    dojo.body().appendChild(
                        newInstanceMenuButton("New chart:", newChart
                                             ).domNode);
                },
                error: function (error) {alert(error)}
            });
        }
    }
}();

dojo.addOnLoad(zc.init);
